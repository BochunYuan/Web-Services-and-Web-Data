"""
Authentication endpoint tests.

Tests the full auth lifecycle:
  register → login → use token → refresh token → access protected endpoint

Each test is INDEPENDENT — they don't share state.
The `client` fixture provides a fresh HTTP client per test.
The `setup_test_db` fixture ensures a clean database.

Test naming convention: test_<what>_<scenario>
  - test_register_success
  - test_register_duplicate_username
  This makes pytest output self-documenting.
"""

import pytest
from httpx import AsyncClient

AUTH = "/api/v1/auth"


class TestRegister:
    """Tests for POST /api/v1/auth/register"""

    async def test_register_success(self, client: AsyncClient, setup_test_db):
        """Happy path: valid registration returns 201 with user data."""
        r = await client.post(f"{AUTH}/register", json={
            "username": "newuser1",
            "email": "newuser1@test.com",
            "password": "ValidPass123",
        })
        assert r.status_code == 201
        body = r.json()
        assert body["username"] == "newuser1"
        assert body["email"] == "newuser1@test.com"
        assert body["is_active"] is True
        # SECURITY: password must never appear in any response
        assert "password" not in body
        assert "hashed_password" not in body

    async def test_register_duplicate_username_returns_409(self, client: AsyncClient, setup_test_db):
        """Registering the same username twice returns 409 Conflict."""
        payload = {"username": "dupuser", "email": "dup1@test.com", "password": "Pass1234"}
        await client.post(f"{AUTH}/register", json=payload)

        # Second registration — same username, different email
        r = await client.post(f"{AUTH}/register", json={
            **payload, "email": "dup2@test.com"
        })
        assert r.status_code == 409
        assert "already registered" in r.json()["detail"].lower()

    async def test_register_weak_password_returns_422(self, client: AsyncClient, setup_test_db):
        """Password without a digit fails Pydantic validation → 422."""
        r = await client.post(f"{AUTH}/register", json={
            "username": "weakuser",
            "email": "weak@test.com",
            "password": "nodigitshere",   # fails: must contain a digit
        })
        assert r.status_code == 422
        # The validation error detail should mention the password field
        errors = r.json()["detail"]
        assert any("password" in str(e).lower() for e in errors)

    async def test_register_invalid_email_returns_422(self, client: AsyncClient, setup_test_db):
        """Invalid email format is caught by Pydantic EmailStr validator."""
        r = await client.post(f"{AUTH}/register", json={
            "username": "bademail",
            "email": "not-an-email",
            "password": "ValidPass123",
        })
        assert r.status_code == 422


class TestLogin:
    """Tests for POST /api/v1/auth/login"""

    async def test_login_success_returns_tokens(self, client: AsyncClient, setup_test_db):
        """Valid credentials return access_token + refresh_token."""
        # Register first
        await client.post(f"{AUTH}/register", json={
            "username": "loginuser", "email": "login@test.com", "password": "LoginPass123"
        })
        # Login
        r = await client.post(f"{AUTH}/login", data={
            "username": "loginuser", "password": "LoginPass123"
        })
        assert r.status_code == 200
        body = r.json()
        assert "access_token" in body
        assert "refresh_token" in body
        assert body["token_type"] == "bearer"
        assert body["expires_in"] == 1800  # 30 min × 60 sec

        # Tokens should be non-empty JWT strings (3 dot-separated parts)
        assert len(body["access_token"].split(".")) == 3
        assert len(body["refresh_token"].split(".")) == 3

    async def test_login_wrong_password_returns_401(self, client: AsyncClient, setup_test_db):
        """Wrong password returns 401 Unauthorized."""
        await client.post(f"{AUTH}/register", json={
            "username": "passuser", "email": "pass@test.com", "password": "CorrectPass123"
        })
        r = await client.post(f"{AUTH}/login", data={
            "username": "passuser", "password": "WrongPassword123"
        })
        assert r.status_code == 401
        # Must include WWW-Authenticate header per OAuth2 spec
        assert "www-authenticate" in r.headers

    async def test_login_nonexistent_user_returns_401(self, client: AsyncClient, setup_test_db):
        """Login with unknown username returns 401 (not 404 — don't reveal user existence)."""
        r = await client.post(f"{AUTH}/login", data={
            "username": "ghost_user_xyz", "password": "SomePass123"
        })
        assert r.status_code == 401


class TestProtectedEndpoints:
    """Tests for JWT-protected routes."""

    async def test_get_me_with_valid_token(self, client: AsyncClient, setup_test_db):
        """GET /auth/me with valid token returns current user profile."""
        await client.post(f"{AUTH}/register", json={
            "username": "meuser", "email": "me@test.com", "password": "MePass123"
        })
        r = await client.post(f"{AUTH}/login", data={
            "username": "meuser", "password": "MePass123"
        })
        token = r.json()["access_token"]

        r = await client.get(f"{AUTH}/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert r.json()["username"] == "meuser"

    async def test_get_me_without_token_returns_401(self, client: AsyncClient, setup_test_db):
        """GET /auth/me without token returns 401."""
        r = await client.get(f"{AUTH}/me")
        assert r.status_code == 401

    async def test_get_me_with_invalid_token_returns_401(self, client: AsyncClient, setup_test_db):
        """Tampered or forged token returns 401."""
        r = await client.get(f"{AUTH}/me", headers={
            "Authorization": "Bearer this.is.notavalidtoken"
        })
        assert r.status_code == 401


class TestRefreshToken:
    """Tests for POST /api/v1/auth/refresh"""

    async def test_refresh_token_returns_new_access_token(self, client: AsyncClient, setup_test_db):
        """Valid refresh token returns a new access token."""
        await client.post(f"{AUTH}/register", json={
            "username": "refreshuser", "email": "refresh@test.com", "password": "RefPass123"
        })
        r = await client.post(f"{AUTH}/login", data={
            "username": "refreshuser", "password": "RefPass123"
        })
        refresh_token = r.json()["refresh_token"]

        r2 = await client.post(f"{AUTH}/refresh", json={"refresh_token": refresh_token})
        assert r2.status_code == 200
        assert "access_token" in r2.json()
        assert r2.json()["token_type"] == "bearer"

    async def test_refresh_with_invalid_token_returns_401(self, client: AsyncClient, setup_test_db):
        """Invalid refresh token returns 401."""
        r = await client.post(f"{AUTH}/refresh", json={"refresh_token": "invalid.token.here"})
        assert r.status_code == 401

    async def test_access_token_cannot_be_used_as_refresh(self, client: AsyncClient, setup_test_db):
        """Access token rejected at /refresh endpoint (wrong token type)."""
        await client.post(f"{AUTH}/register", json={
            "username": "tokentype", "email": "type@test.com", "password": "TypePass123"
        })
        r = await client.post(f"{AUTH}/login", data={
            "username": "tokentype", "password": "TypePass123"
        })
        # Use the ACCESS token (not refresh) at the refresh endpoint
        access_token = r.json()["access_token"]
        r2 = await client.post(f"{AUTH}/refresh", json={"refresh_token": access_token})
        assert r2.status_code == 401
