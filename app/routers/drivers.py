"""
Driver CRUD endpoints — /api/v1/drivers

Demonstrates all four CRUD operations plus:
  - Pagination (page/limit query params)
  - Filtering (by nationality and surname search)
  - JWT-protected write operations
  - Proper HTTP status codes: 200, 201, 204, 404, 409, 422
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from typing import Optional

from app.database import get_db
from app.models.driver import Driver
from app.schemas.driver import DriverCreate, DriverUpdate, DriverResponse
from app.utils.pagination import PaginationParams, PagedResponse
from app.utils.db_errors import commit_or_raise_conflict
from app.core.dependencies import get_current_active_user
from app.models.user import User

router = APIRouter()


@router.get(
    "",
    response_model=PagedResponse[DriverResponse],
    summary="List all drivers",
    description="""
Retrieve a paginated list of Formula 1 drivers.

**Filters:**
- `nationality`: filter by nationality (e.g. `British`, `German`)
- `search`: search by surname (case-insensitive, partial match)

**Pagination:**
- `page`: page number (default: 1)
- `limit`: items per page (default: 20, max: 100)
    """,
)
async def list_drivers(
    pagination: PaginationParams = Depends(),
    nationality: Optional[str] = Query(default=None, description="Filter by nationality"),
    search: Optional[str] = Query(default=None, description="Search by surname (partial match)"),
    db: AsyncSession = Depends(get_db),
) -> PagedResponse[DriverResponse]:
    # Build base query — we apply filters progressively
    query = select(Driver)
    count_query = select(func.count()).select_from(Driver)

    # Apply filters if provided
    # ilike = case-insensitive LIKE (works in both SQLite and MySQL)
    if nationality:
        query = query.where(Driver.nationality.ilike(f"%{nationality}%"))
        count_query = count_query.where(Driver.nationality.ilike(f"%{nationality}%"))
    if search:
        query = query.where(Driver.surname.ilike(f"%{search}%"))
        count_query = count_query.where(Driver.surname.ilike(f"%{search}%"))

    # Get total count (for pagination metadata)
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    # Apply ordering, offset, limit — order by surname for consistent results
    query = query.order_by(Driver.surname).offset(pagination.offset).limit(pagination.limit)
    result = await db.execute(query)
    drivers = result.scalars().all()

    return PagedResponse.create(items=list(drivers), total=total, pagination=pagination)


@router.get(
    "/{driver_id}",
    response_model=DriverResponse,
    summary="Get a driver by ID",
)
async def get_driver(
    driver_id: int,
    db: AsyncSession = Depends(get_db),
) -> DriverResponse:
    result = await db.execute(select(Driver).where(Driver.id == driver_id))
    driver = result.scalar_one_or_none()
    if driver is None:
        # 404 Not Found — the standard response when a resource doesn't exist
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Driver {driver_id} not found")
    return driver


@router.post(
    "",
    response_model=DriverResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new driver",
    description="Requires authentication. Returns 409 if driver_ref already exists.",
)
async def create_driver(
    data: DriverCreate,
    db: AsyncSession = Depends(get_db),
    # Depends(get_current_active_user): FastAPI calls this before our handler.
    # If the token is missing/invalid, it returns 401 automatically.
    # The underscore prefix (_) signals we don't use the value — just need the auth check.
    _: User = Depends(get_current_active_user),
) -> DriverResponse:
    # Check for duplicate driver_ref
    existing = await db.execute(select(Driver).where(Driver.driver_ref == data.driver_ref))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"driver_ref '{data.driver_ref}' already exists")

    driver = Driver(**data.model_dump())
    db.add(driver)
    await commit_or_raise_conflict(db, detail=f"driver_ref '{data.driver_ref}' already exists")
    await db.refresh(driver)
    return driver


@router.put(
    "/{driver_id}",
    response_model=DriverResponse,
    summary="Update a driver",
    description="Requires authentication. Only provided fields are updated (partial update).",
)
async def update_driver(
    driver_id: int,
    data: DriverUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> DriverResponse:
    result = await db.execute(select(Driver).where(Driver.id == driver_id))
    driver = result.scalar_one_or_none()
    if driver is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Driver {driver_id} not found")

    # model_dump(exclude_unset=True): only returns fields the client explicitly sent.
    # This means PATCH-style partial updates: sending {"nationality": "British"}
    # only changes nationality, leaving all other fields untouched.
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(driver, field, value)

    await db.commit()
    await db.refresh(driver)
    return driver


@router.delete(
    "/{driver_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a driver",
    description="Requires authentication. Returns 204 No Content on success (no response body).",
)
async def delete_driver(
    driver_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> None:
    result = await db.execute(select(Driver).where(Driver.id == driver_id))
    driver = result.scalar_one_or_none()
    if driver is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Driver {driver_id} not found")

    await db.delete(driver)
    await db.commit()
    # 204 No Content: success but no body — the standard for DELETE operations
    return None
