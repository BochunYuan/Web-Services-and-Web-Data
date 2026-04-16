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


async def commit_or_raise_conflict(db: AsyncSession, detail: str) -> None:
    """
    Commit a session, converting unique-key violations into HTTP 409 responses.
    """
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        if is_unique_constraint_error(exc):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=detail,
            ) from exc
        raise
