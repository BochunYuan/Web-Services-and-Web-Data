"""
Driver CRUD endpoint tests.

Covers: list, get, create, update, delete + pagination + filters.

These tests use the `seed_f1_data` fixture which pre-populates
Hamilton (id=1) and Verstappen (id=2) into the test database.

Tests that write data (POST/PUT/DELETE) use `auth_client` (pre-authenticated).
Tests that only read data use the plain `client` fixture.
"""

import pytest
from httpx import AsyncClient

DRIVERS = "/api/v1/drivers"


class TestListDrivers:
    """Tests for GET /api/v1/drivers"""

    async def test_list_returns_paginated_response(self, client: AsyncClient, seed_f1_data):
        """List endpoint returns pagination metadata alongside items."""
        r = await client.get(DRIVERS)
        assert r.status_code == 200
        body = r.json()
        # Must have all pagination fields
        for key in ["items", "total", "page", "limit", "pages", "has_next", "has_prev"]:
            assert key in body, f"Missing pagination field: {key}"

    async def test_list_contains_seeded_drivers(self, client: AsyncClient, seed_f1_data):
        """Seeded drivers (Hamilton, Verstappen) appear in the list."""
        r = await client.get(DRIVERS)
        assert r.status_code == 200
        surnames = [d["surname"] for d in r.json()["items"]]
        assert "Hamilton" in surnames
        assert "Verstappen" in surnames

    async def test_filter_by_nationality(self, client: AsyncClient, seed_f1_data):
        """?nationality=British returns only British drivers."""
        r = await client.get(f"{DRIVERS}?nationality=British")
        assert r.status_code == 200
        items = r.json()["items"]
        assert len(items) >= 1
        assert all(d["nationality"] == "British" for d in items)

    async def test_search_by_surname(self, client: AsyncClient, seed_f1_data):
        """?search=verstappen finds Verstappen (case-insensitive)."""
        r = await client.get(f"{DRIVERS}?search=verstappen")
        assert r.status_code == 200
        items = r.json()["items"]
        assert any("Verstappen" in d["surname"] for d in items)

    async def test_pagination_limit_respected(self, client: AsyncClient, seed_f1_data):
        """?limit=1 returns exactly 1 item."""
        r = await client.get(f"{DRIVERS}?limit=1")
        assert r.status_code == 200
        assert len(r.json()["items"]) == 1

    async def test_limit_above_max_returns_422(self, client: AsyncClient, seed_f1_data):
        """?limit=101 exceeds maximum (100) → 422 Unprocessable Entity."""
        r = await client.get(f"{DRIVERS}?limit=101")
        assert r.status_code == 422

    async def test_page_zero_returns_422(self, client: AsyncClient, seed_f1_data):
        """?page=0 is invalid (pages are 1-indexed) → 422."""
        r = await client.get(f"{DRIVERS}?page=0")
        assert r.status_code == 422


class TestGetDriver:
    """Tests for GET /api/v1/drivers/{id}"""

    async def test_get_existing_driver(self, client: AsyncClient, seed_f1_data):
        """Get Hamilton by ID — returns correct data."""
        r = await client.get(f"{DRIVERS}/1")
        assert r.status_code == 200
        body = r.json()
        assert body["id"] == 1
        assert body["surname"] == "Hamilton"
        assert body["nationality"] == "British"
        assert body["code"] == "HAM"

    async def test_get_nonexistent_driver_returns_404(self, client: AsyncClient, seed_f1_data):
        """Non-existent driver ID returns 404 Not Found."""
        r = await client.get(f"{DRIVERS}/99999")
        assert r.status_code == 404
        assert "not found" in r.json()["detail"].lower()


class TestCreateDriver:
    """Tests for POST /api/v1/drivers"""

    async def test_create_driver_authenticated(self, auth_client: AsyncClient, seed_f1_data):
        """Authenticated user can create a new driver → 201."""
        r = await auth_client.post(DRIVERS, json={
            "driver_ref": "leclerc",
            "forename": "Charles",
            "surname": "Leclerc",
            "nationality": "Monegasque",
            "driver_number": 16,
            "code": "LEC",
        })
        assert r.status_code == 201
        body = r.json()
        assert body["surname"] == "Leclerc"
        assert body["id"] is not None   # DB assigned an ID
        assert "hashed_password" not in body  # no credential leakage

    async def test_create_driver_unauthenticated_returns_401(self, client: AsyncClient, seed_f1_data):
        """Creating a driver without a token returns 401."""
        r = await client.post(DRIVERS, json={
            "driver_ref": "noauth_driver",
            "forename": "No", "surname": "Auth",
        })
        assert r.status_code == 401

    async def test_create_duplicate_driver_ref_returns_409(self, auth_client: AsyncClient, seed_f1_data):
        """driver_ref must be unique — duplicate returns 409 Conflict."""
        r = await auth_client.post(DRIVERS, json={
            "driver_ref": "hamilton",  # already exists in seed data
            "forename": "Fake", "surname": "Hamilton",
        })
        assert r.status_code == 409

    async def test_create_driver_missing_required_field_returns_422(self, auth_client: AsyncClient, seed_f1_data):
        """Missing required `driver_ref` → 422 Validation Error."""
        r = await auth_client.post(DRIVERS, json={
            "forename": "No", "surname": "Ref",
            # driver_ref is required but omitted
        })
        assert r.status_code == 422


class TestUpdateDriver:
    """Tests for PUT /api/v1/drivers/{id}"""

    async def test_update_driver_authenticated(self, auth_client: AsyncClient, seed_f1_data):
        """Authenticated user can update a driver's nationality."""
        r = await auth_client.put(f"{DRIVERS}/2", json={"nationality": "Belgian"})
        assert r.status_code == 200
        assert r.json()["nationality"] == "Belgian"

    async def test_update_nonexistent_driver_returns_404(self, auth_client: AsyncClient, seed_f1_data):
        """Updating a non-existent driver returns 404."""
        r = await auth_client.put(f"{DRIVERS}/99999", json={"nationality": "French"})
        assert r.status_code == 404

    async def test_update_unauthenticated_returns_401(self, client: AsyncClient, seed_f1_data):
        """PUT without token returns 401."""
        r = await client.put(f"{DRIVERS}/1", json={"nationality": "American"})
        assert r.status_code == 401


class TestDeleteDriver:
    """Tests for DELETE /api/v1/drivers/{id}"""

    async def test_delete_driver_authenticated(self, auth_client: AsyncClient, seed_f1_data):
        """Create then delete a driver — 204 on delete, 404 on subsequent get."""
        # Create a driver to delete (don't delete seeded data used by other tests)
        r = await auth_client.post(DRIVERS, json={
            "driver_ref": "to_delete_driver",
            "forename": "Delete", "surname": "Me",
        })
        assert r.status_code == 201
        new_id = r.json()["id"]

        # Delete it
        r = await auth_client.delete(f"{DRIVERS}/{new_id}")
        assert r.status_code == 204
        assert r.content == b""  # 204 No Content has empty body

        # Confirm it's gone
        r = await auth_client.get(f"{DRIVERS}/{new_id}")
        assert r.status_code == 404

    async def test_delete_unauthenticated_returns_401(self, client: AsyncClient, seed_f1_data):
        """DELETE without token returns 401."""
        r = await client.delete(f"{DRIVERS}/1")
        assert r.status_code == 401
