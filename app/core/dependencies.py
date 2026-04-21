"""
FastAPI dependency functions.

Dependencies are functions that FastAPI calls automatically before a route
handler runs. They handle cross-cutting concerns like:
  - Providing a database session
  - Extracting and verifying the current user from a JWT token

Usage in a router:
    @router.get("/protected")
    async def protected_route(
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ):
        return {"username": current_user.username}

FastAPI sees `Depends(get_current_user)` and automatically:
  1. Extracts the Authorization header
  2. Validates the JWT
  3. Looks up the user in the database
  4. Either passes the User object to the handler, or returns 401
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.user import User
from app.core.security import decode_access_token

# ---------------------------------------------------------------------------
# OAuth2PasswordBearer
# ---------------------------------------------------------------------------
# This tells FastAPI:
#   1. The token comes from the "Authorization: Bearer <token>" header
#   2. The URL where a client can GET a token is /api/v1/auth/login
#      (used by Swagger UI to show a "Authorize" button)
#
# auto_error=True (default): if no Authorization header is present,
#   FastAPI automatically returns 401 before even calling your route handler.

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


# ---------------------------------------------------------------------------
# get_current_user — the core authentication dependency
# ---------------------------------------------------------------------------

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Extract and validate the current user from the JWT access token.

    Flow:
      1. FastAPI extracts the Bearer token from the Authorization header
         (oauth2_scheme handles this automatically)
      2. We decode the JWT to get the username
      3. We look up the user in the database
      4. If anything fails → 401 Unauthorized

    The 401 response always uses the same vague message ("Could not validate
    credentials") regardless of what went wrong — this is intentional security
    practice. We don't tell attackers whether the token was expired, forged,
    or the user doesn't exist.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        # WWW-Authenticate header is required by the OAuth2 spec
        # It tells the client what authentication scheme to use
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Step 1: decode JWT
    username = decode_access_token(token)
    if username is None:
        raise credentials_exception

    # Step 2: look up user in DB
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Like get_current_user, but also checks if the account is active.

    Use this instead of get_current_user for endpoints that should be
    blocked for suspended/disabled accounts.

    Why a separate dependency?
      - get_current_user: "is this a valid token for a real user?"
      - get_current_active_user: "is this user allowed to act right now?"
    This separation lets us e.g. allow inactive users to call /auth/me
    to see their status, but block them from all other endpoints.
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )
    return current_user
