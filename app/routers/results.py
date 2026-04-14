"""
Result read-only endpoints — /api/v1/results

Results are imported from CSV and not editable via the API.
Supports filtering by race_id or driver_id — the two most common use cases.
These filtered queries are what the analytics endpoints build on.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional

from app.database import get_db
from app.models.result import Result
from app.schemas.result import ResultResponse
from app.utils.pagination import PaginationParams, PagedResponse

router = APIRouter()


@router.get(
    "",
    response_model=PagedResponse[ResultResponse],
    summary="List race results",
    description="""
Paginated list of race results.

**Filters (at least one recommended for performance):**
- `race_id`: all results for a specific race (e.g. all drivers in 2023 Bahrain GP)
- `driver_id`: all results for a specific driver (career history)
- `status`: filter by finish status (e.g. `Finished`, `Engine`, `Collision`)
    """,
)
async def list_results(
    pagination: PaginationParams = Depends(),
    race_id: Optional[int] = Query(default=None, description="Filter by race ID"),
    driver_id: Optional[int] = Query(default=None, description="Filter by driver ID"),
    status_filter: Optional[str] = Query(default=None, alias="status", description="Filter by finish status"),
    db: AsyncSession = Depends(get_db),
) -> PagedResponse[ResultResponse]:
    query = select(Result)
    count_query = select(func.count()).select_from(Result)

    if race_id:
        query = query.where(Result.race_id == race_id)
        count_query = count_query.where(Result.race_id == race_id)
    if driver_id:
        query = query.where(Result.driver_id == driver_id)
        count_query = count_query.where(Result.driver_id == driver_id)
    if status_filter:
        query = query.where(Result.status.ilike(f"%{status_filter}%"))
        count_query = count_query.where(Result.status.ilike(f"%{status_filter}%"))

    total = (await db.execute(count_query)).scalar_one()
    # Order by race_id, then position — natural reading order
    query = query.order_by(Result.race_id, Result.position_order).offset(pagination.offset).limit(pagination.limit)
    results = (await db.execute(query)).scalars().all()

    return PagedResponse.create(items=list(results), total=total, pagination=pagination)


@router.get("/{result_id}", response_model=ResultResponse, summary="Get a result by ID")
async def get_result(result_id: int, db: AsyncSession = Depends(get_db)) -> ResultResponse:
    result = (await db.execute(select(Result).where(Result.id == result_id))).scalar_one_or_none()
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Result {result_id} not found")
    return result
