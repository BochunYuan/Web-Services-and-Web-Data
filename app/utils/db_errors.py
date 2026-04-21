"""
Helpers for translating low-level database integrity errors into API responses.
"""

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession


def is_unique_constraint_error(exc: IntegrityError) -> bool:
    """Best-effort detection for unique-key violations across SQLite/MySQL."""
    message = str(getattr(exc, "orig", exc)).lower()
    markers = (
        "unique constraint failed",
        "duplicate entry",
        "duplicate key",
        "is not unique",
        "unique failed",
    )
    return any(marker in message for marker in markers)


async def flush_or_raise_conflict(db: AsyncSession, detail: str) -> None:
    """
    Flush pending SQL, converting unique-key violations into HTTP 409 responses.

    Request-scoped dependencies own the final transaction commit. Write handlers
    use this helper when they need database-generated values or integrity errors
    before returning the response.
    """
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        if is_unique_constraint_error(exc):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=detail,
            ) from exc
        raise
