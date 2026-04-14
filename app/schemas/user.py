"""
Pydantic schemas for User and Authentication.

Key concept: Pydantic schemas ≠ SQLAlchemy models.

  SQLAlchemy model (app/models/user.py):
    - Defines the DATABASE table structure
    - Contains hashed_password — never sent to clients
    - Has relationships to other tables

  Pydantic schema (this file):
    - Defines what data comes IN (requests) and goes OUT (responses)
    - Input schemas validate and sanitize user data before it touches the DB
    - Response schemas control exactly what fields are exposed via the API
    - hashed_password NEVER appears in any response schema

This separation is the standard FastAPI pattern for preventing accidental
data leakage (e.g. accidentally returning password hashes in API responses).
"""

from pydantic import BaseModel, EmailStr, Field, field_validator
from datetime import datetime
from typing import Optional
import re


# ---------------------------------------------------------------------------
# Request schemas (what the CLIENT sends to the server)
# ---------------------------------------------------------------------------

class UserRegister(BaseModel):
    """
    Schema for POST /auth/register

    Field validators run automatically when FastAPI receives a request.
    If validation fails, FastAPI returns 422 Unprocessable Entity with
    a detailed error message — no custom error handling needed.
    """
    username: str = Field(
        min_length=3,
        max_length=50,
        description="Unique username (3-50 characters, alphanumeric + underscores)",
        examples=["hamilton44"],
    )
    email: EmailStr = Field(
        description="Valid email address",
        examples=["lewis@mercedes.com"],
    )
    password: str = Field(
        min_length=8,
        max_length=100,
        description="Password (min 8 characters)",
        examples=["SecurePass123!"],
    )

    @field_validator("username")
    @classmethod
    def username_alphanumeric(cls, v: str) -> str:
        """Only allow letters, numbers, and underscores in usernames."""
        if not re.match(r"^[a-zA-Z0-9_]+$", v):
            raise ValueError("Username may only contain letters, numbers, and underscores")
        return v.lower()  # normalise to lowercase for consistency

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        """Enforce basic password strength: at least one letter and one digit."""
        if not re.search(r"[A-Za-z]", v):
            raise ValueError("Password must contain at least one letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit")
        return v


class UserLogin(BaseModel):
    """
    Schema for POST /auth/login (JSON body variant).

    Note: FastAPI also supports OAuth2 form-data login (username/password fields)
    via OAuth2PasswordRequestForm. We support both for flexibility.
    """
    username: str = Field(examples=["hamilton44"])
    password: str = Field(examples=["SecurePass123!"])


class RefreshTokenRequest(BaseModel):
    """Schema for POST /auth/refresh"""
    refresh_token: str


# ---------------------------------------------------------------------------
# Response schemas (what the SERVER sends back to the client)
# ---------------------------------------------------------------------------

class UserResponse(BaseModel):
    """
    Public user information returned by the API.

    Critically: hashed_password is NOT here.
    `model_config = ConfigDict(from_attributes=True)` tells Pydantic to read
    attributes from SQLAlchemy ORM objects (not just plain dicts).
    """
    id: int
    username: str
    email: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    """
    Authentication token pair returned after login or registration.

    access_token:  short-lived, sent with every API request
    refresh_token: long-lived, stored securely by client, used only to refresh
    token_type:    always "bearer" (OAuth2 standard)
    """
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds until access_token expires


class AccessTokenResponse(BaseModel):
    """Returned by POST /auth/refresh — only a new access token."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
