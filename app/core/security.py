"""
Security utilities: password hashing and JWT token management.

This module is the single source of truth for all cryptographic operations.
Nothing else in the codebase should touch passwords or tokens directly —
everything goes through these functions.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings

# ---------------------------------------------------------------------------
# Password hashing — bcrypt
# ---------------------------------------------------------------------------
# CryptContext is passlib's abstraction layer over hashing algorithms.
#
# Why bcrypt?
#   - "slow by design": bcrypt intentionally takes ~100ms to hash a password.
#     This makes brute-force attacks impractical even if the database leaks.
#   - MD5/SHA1 hash in microseconds — an attacker with the DB can crack
#     millions of passwords per second. bcrypt limits them to ~10/second.
#
# deprecated="auto": if we ever switch algorithms in the future, passlib
#   will transparently re-hash old passwords on next login (migration-free).

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    """
    Hash a plain-text password using bcrypt.

    Example:
        hash_password("mypassword123")
        → "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW"

    The resulting string is self-contained — it includes the algorithm,
    cost factor (rounds), salt, and hash. passlib can verify it without
    storing the salt separately.
    """
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain-text password against its bcrypt hash.

    Returns True if they match, False otherwise.
    Timing-safe: takes the same time regardless of where the mismatch is,
    preventing timing attacks.
    """
    return pwd_context.verify(plain_password, hashed_password)


# ---------------------------------------------------------------------------
# JWT Token creation
# ---------------------------------------------------------------------------
# JWT (JSON Web Token) structure:  header.payload.signature
#
# header:    {"alg": "HS256", "typ": "JWT"}
# payload:   {"sub": "username", "exp": 1234567890, "type": "access"}
# signature: HMAC-SHA256(base64(header) + "." + base64(payload), SECRET_KEY)
#
# The signature makes the token tamper-proof: if anyone changes the payload
# (e.g. extends expiry or changes username), the signature won't match.
# Verification only requires the SECRET_KEY — no database lookup needed.
#
# Why TWO tokens (access + refresh)?
#   - access_token:  short-lived (30 min). Used on every API call.
#     If stolen, damage is limited to 30 minutes.
#   - refresh_token: long-lived (7 days). Used ONLY to get a new access token.
#     Client stores this securely; it's never sent to most endpoints.
#   This is the industry-standard pattern used by Google, GitHub, etc.

def _create_token(data: dict, expires_delta: timedelta, token_type: str) -> str:
    """
    Internal helper: create a signed JWT with an expiry time.

    `token_type` is stored in the payload so we can reject a refresh token
    being used as an access token (and vice versa).
    """
    payload = data.copy()
    expire = datetime.now(timezone.utc) + expires_delta
    payload.update({
        "exp": expire,
        "iat": datetime.now(timezone.utc),  # issued-at
        "type": token_type,
    })
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_access_token(subject: str) -> str:
    """
    Create a short-lived access token for a given username.

    `sub` (subject) is the standard JWT claim for "who this token belongs to".
    """
    return _create_token(
        data={"sub": subject},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        token_type="access",
    )


def create_refresh_token(subject: str) -> str:
    """
    Create a long-lived refresh token for a given username.
    """
    return _create_token(
        data={"sub": subject},
        expires_delta=timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        token_type="refresh",
    )


# ---------------------------------------------------------------------------
# JWT Token verification
# ---------------------------------------------------------------------------

def decode_token(token: str, expected_type: str) -> Optional[str]:
    """
    Decode and verify a JWT token. Returns the subject (username) if valid.

    Returns None if:
      - Signature is invalid (tampered token)
      - Token has expired
      - Token type doesn't match (e.g. refresh token used as access token)
      - Any other JWT error

    We return None rather than raising here so callers can decide how to
    respond (the router layer raises HTTPException with the right status code).
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        subject: Optional[str] = payload.get("sub")
        token_type: Optional[str] = payload.get("type")

        if subject is None or token_type != expected_type:
            return None

        return subject

    except JWTError:
        # Covers: ExpiredSignatureError, DecodeError, InvalidAlgorithmError, etc.
        return None


def decode_access_token(token: str) -> Optional[str]:
    return decode_token(token, expected_type="access")


def decode_refresh_token(token: str) -> Optional[str]:
    return decode_token(token, expected_type="refresh")
