"""
Authentication endpoints.

Registered at prefix /api/v1/auth in main.py.

Endpoints:
  POST /api/v1/auth/register  — create new account
  POST /api/v1/auth/login     — get token pair with OAuth2 form data
  POST /api/v1/auth/login/json — get token pair with a JSON body
  POST /api/v1/auth/refresh   — exchange refresh token for new access token
  GET  /api/v1/auth/me        — get current user info (requires valid access token)
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.user import (
    UserRegister,
    UserLogin,
    UserResponse,
    TokenResponse,
    AccessTokenResponse,
    RefreshTokenRequest,
)
from app.services.auth_service import register_user, authenticate_user, create_token_pair
from app.core.security import decode_refresh_token, create_access_token
from app.core.dependencies import get_current_active_user
from app.models.user import User
from app.config import settings

router = APIRouter()


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
    description="""
Create a new user account with a username, email, and password.

**Password requirements:**
- Minimum 8 characters
- Must contain at least one letter
- Must contain at least one digit

Returns the created user profile (without password).
    """,
)
async def register(
    data: UserRegister,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    user = await register_user(db, data)
    return user


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login and receive JWT tokens",
    description="""
Authenticate with username and password.

Returns an **access token** (valid 30 minutes) and a **refresh token** (valid 7 days).

Include the access token in subsequent requests:
```
Authorization: Bearer <access_token>
```

This endpoint accepts **form data** in the OAuth2 password-flow format
used by Swagger UI's Authorize button.

For JSON clients, use `POST /api/v1/auth/login/json` with
`{"username": "...", "password": "..."}`.
    """,
)
async def login(
    db: AsyncSession = Depends(get_db),
    # OAuth2PasswordRequestForm parses application/x-www-form-urlencoded
    # This is what Swagger UI's "Authorize" button sends
    form_data: OAuth2PasswordRequestForm = Depends(),
) -> TokenResponse:
    user = await authenticate_user(db, form_data.username, form_data.password)
    return create_token_pair(user.username)


@router.post(
    "/login/json",
    response_model=TokenResponse,
    summary="Login with JSON body",
    description="Alternative login endpoint accepting JSON (for clients that prefer JSON over form data).",
)
async def login_json(
    data: UserLogin,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    user = await authenticate_user(db, data.username, data.password)
    return create_token_pair(user.username)


@router.post(
    "/refresh",
    response_model=AccessTokenResponse,
    summary="Refresh access token",
    description="""
Exchange a valid **refresh token** for a new **access token**.

Use this when your access token expires (after 30 minutes) without requiring
the user to log in again.

The refresh token itself remains valid for 7 days.
    """,
)
async def refresh_token(
    data: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
) -> AccessTokenResponse:
    # Decode and validate the refresh token
    username = decode_refresh_token(data.refresh_token)
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verify user still exists and is active
    from sqlalchemy import select
    result = await db.execute(
        select(User).where(User.username == username, User.is_active == True)
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or account disabled",
        )

    return {
        "access_token": create_access_token(username),
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user profile",
    description="""
Returns the profile of the currently authenticated user.

Requires a valid **access token** in the Authorization header:
```
Authorization: Bearer <access_token>
```
    """,
)
async def get_me(
    current_user: User = Depends(get_current_active_user),
) -> UserResponse:
    # get_current_active_user dependency handles all validation
    # If we reach here, current_user is guaranteed to be valid and active
    return current_user
