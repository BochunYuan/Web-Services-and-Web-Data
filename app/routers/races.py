"""
Race CRUD endpoints — /api/v1/races

Races include nested circuit info (JOIN-loaded) in responses.
Filter by year to browse a full season's calendar.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from typing import Optional

from app.database import get_db
from app.models.race import Race
from app.schemas.race import RaceCreate, RaceUpdate, RaceResponse
from app.utils.pagination import PaginationParams, PagedResponse
from app.utils.db_errors import flush_or_raise_conflict
from app.core.dependencies import get_current_active_user
from app.models.user import User

router = APIRouter()


@router.get(
    "",
    response_model=PagedResponse[RaceResponse],
    summary="List all races",
    description="""
Paginated list of F1 races. Each race includes nested circuit information.

**Filters:**
- `year`: filter by season year (e.g. `2023`)
- `search`: search by race name (e.g. `Monaco`)
    """,
)
async def list_races(
    pagination: PaginationParams = Depends(),
    year: Optional[int] = Query(default=None, ge=1950, le=2030, description="Filter by season year"),
    search: Optional[str] = Query(default=None, description="Search by race name"),
    db: AsyncSession = Depends(get_db),
) -> PagedResponse[RaceResponse]:
    # selectinload: eagerly load the circuit relationship in a second query
    # This avoids N+1 queries (one per race) while keeping the query simple
    query = select(Race).options(selectinload(Race.circuit))
    count_query = select(func.count()).select_from(Race)

    if year:
        query = query.where(Race.year == year)
        count_query = count_query.where(Race.year == year)
    if search:
        query = query.where(Race.name.ilike(f"%{search}%"))
        count_query = count_query.where(Race.name.ilike(f"%{search}%"))

    total = (await db.execute(count_query)).scalar_one()
    # Order by year desc, then round asc — most recent season first
    query = query.order_by(Race.year.desc(), Race.round.asc()).offset(pagination.offset).limit(pagination.limit)
    races = (await db.execute(query)).scalars().all()

    return PagedResponse.create(items=list(races), total=total, pagination=pagination)


@router.get("/{race_id}", response_model=RaceResponse, summary="Get a race by ID")
async def get_race(race_id: int, db: AsyncSession = Depends(get_db)) -> RaceResponse:
    result = await db.execute(
        select(Race).options(selectinload(Race.circuit)).where(Race.id == race_id)
    )
    race = result.scalar_one_or_none()
    if race is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Race {race_id} not found")
    return race


@router.post(
    "",
    response_model=RaceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new race",
)
async def create_race(
    data: RaceCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> RaceResponse:
    # Enforce unique (year, round) constraint
    existing = (await db.execute(
        select(Race).where(Race.year == data.year, Race.round == data.round)
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Race already exists for year={data.year}, round={data.round}",
        )

    d = data.model_dump()
    d["date"] = d.pop("race_date", None)
    d["time"] = d.pop("race_time", None)
    race = Race(**d)
    db.add(race)
    await flush_or_raise_conflict(
        db,
        detail=f"Race already exists for year={data.year}, round={data.round}",
    )
    # Re-fetch with circuit loaded
    result = await db.execute(select(Race).options(selectinload(Race.circuit)).where(Race.id == race.id))
    return result.scalar_one()


@router.put("/{race_id}", response_model=RaceResponse, summary="Update a race")
async def update_race(
    race_id: int,
    data: RaceUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> RaceResponse:
    race = (await db.execute(select(Race).where(Race.id == race_id))).scalar_one_or_none()
    if race is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Race {race_id} not found")

    update_data = data.model_dump(exclude_unset=True)
    if "race_date" in update_data:
        update_data["date"] = update_data.pop("race_date")
    if "race_time" in update_data:
        update_data["time"] = update_data.pop("race_time")
    for field, value in update_data.items():
        setattr(race, field, value)

    await db.flush()
    result = await db.execute(select(Race).options(selectinload(Race.circuit)).where(Race.id == race_id))
    return result.scalar_one()


@router.delete("/{race_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a race")
async def delete_race(
    race_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> None:
    race = (await db.execute(select(Race).where(Race.id == race_id))).scalar_one_or_none()
    if race is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Race {race_id} not found")
    await db.delete(race)
    await db.flush()
