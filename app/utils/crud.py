"""
Lightweight helpers for shared CRUD operations in API routers.

The goal is to remove repetitive boilerplate without hiding route-specific
validation, authentication, or response-shaping logic.
"""

from __future__ import annotations

from typing import Any, Iterable, TypeVar

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.db_errors import flush_or_raise_conflict

ModelT = TypeVar("ModelT")


async def get_or_404(
    db: AsyncSession,
    model: type[ModelT],
    resource_id: int,
    *,
    resource_name: str,
    options: Iterable[Any] = (),
) -> ModelT:
    """Load a row by integer primary key or raise a consistent 404 response."""
    query = select(model).where(model.id == resource_id)
    if options:
        query = query.options(*options)

    instance = (await db.execute(query)).scalar_one_or_none()
    if instance is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{resource_name} {resource_id} not found",
        )
    return instance


def apply_partial_update(instance: Any, schema: Any) -> dict[str, Any]:
    """Apply only explicitly provided fields from a Pydantic update schema."""
    update_data = schema.model_dump(exclude_unset=True)
    apply_update_data(instance, update_data)
    return update_data


def apply_update_data(instance: Any, update_data: dict[str, Any]) -> dict[str, Any]:
    """Apply a plain field/value mapping to an ORM instance in-place."""
    for field, value in update_data.items():
        setattr(instance, field, value)
    return update_data


async def flush_and_refresh(db: AsyncSession, instance: ModelT) -> ModelT:
    """Flush pending writes and refresh the ORM instance from the database."""
    await db.flush()
    await db.refresh(instance)
    return instance


async def add_and_flush_or_409(
    db: AsyncSession,
    instance: ModelT,
    *,
    conflict_detail: str,
) -> ModelT:
    """Add an ORM instance and translate unique-key violations into HTTP 409."""
    db.add(instance)
    await flush_or_raise_conflict(db, detail=conflict_detail)
    return instance


async def add_flush_refresh_or_409(
    db: AsyncSession,
    instance: ModelT,
    *,
    conflict_detail: str,
) -> ModelT:
    """Add, flush with 409 handling, then refresh a newly created ORM instance."""
    await add_and_flush_or_409(db, instance, conflict_detail=conflict_detail)
    await db.refresh(instance)
    return instance


async def delete_and_flush(db: AsyncSession, instance: Any) -> None:
    """Delete an ORM instance and flush the change within the current transaction."""
    await db.delete(instance)
    await db.flush()
