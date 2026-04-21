"""
Team (Constructor) CRUD endpoints — /api/v1/teams
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from typing import Optional

from app.database import get_db
from app.models.team import Team
from app.schemas.team import TeamCreate, TeamUpdate, TeamResponse
from app.services import cache_service
from app.utils.pagination import PaginationParams, PagedResponse
from app.utils.crud import (
    add_flush_refresh_or_409,
    apply_partial_update,
    delete_and_flush,
    flush_and_refresh,
    get_or_404,
)
from app.core.dependencies import get_current_active_user
from app.models.user import User

router = APIRouter()


@router.get(
    "",
    response_model=PagedResponse[TeamResponse],
    summary="List all teams",
    description="Paginated list of F1 constructors. Filter by `nationality` or search by `name`.",
)
async def list_teams(
    pagination: PaginationParams = Depends(),
    nationality: Optional[str] = Query(default=None, description="Filter by nationality"),
    search: Optional[str] = Query(default=None, description="Search by team name"),
    db: AsyncSession = Depends(get_db),
) -> PagedResponse[TeamResponse]:
    query = select(Team)
    count_query = select(func.count()).select_from(Team)

    if nationality:
        query = query.where(Team.nationality.ilike(f"%{nationality}%"))
        count_query = count_query.where(Team.nationality.ilike(f"%{nationality}%"))
    if search:
        query = query.where(Team.name.ilike(f"%{search}%"))
        count_query = count_query.where(Team.name.ilike(f"%{search}%"))

    total = (await db.execute(count_query)).scalar_one()
    query = query.order_by(Team.name).offset(pagination.offset).limit(pagination.limit)
    teams = (await db.execute(query)).scalars().all()

    return PagedResponse.create(items=list(teams), total=total, pagination=pagination)


@router.get("/{team_id}", response_model=TeamResponse, summary="Get a team by ID")
async def get_team(team_id: int, db: AsyncSession = Depends(get_db)) -> TeamResponse:
    return await get_or_404(db, Team, team_id, resource_name="Team")


@router.post(
    "",
    response_model=TeamResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new team",
    description="""
Requires authentication. Creates a new team record for demo or extension scenarios and
does not modify existing constructors unless you explicitly call `PUT /api/v1/teams/{team_id}`.
    """,
)
async def create_team(
    data: TeamCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> TeamResponse:
    existing = (await db.execute(select(Team).where(Team.constructor_ref == data.constructor_ref))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"constructor_ref '{data.constructor_ref}' already exists")

    team = Team(**data.model_dump())
    cache_service.mark_domain_data_changed(db)
    return await add_flush_refresh_or_409(
        db,
        team,
        conflict_detail=f"constructor_ref '{data.constructor_ref}' already exists",
    )


@router.put("/{team_id}", response_model=TeamResponse, summary="Update a team")
async def update_team(
    team_id: int,
    data: TeamUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> TeamResponse:
    team = await get_or_404(db, Team, team_id, resource_name="Team")

    apply_partial_update(team, data)
    cache_service.mark_domain_data_changed(db)

    return await flush_and_refresh(db, team)


@router.delete("/{team_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a team")
async def delete_team(
    team_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> None:
    team = await get_or_404(db, Team, team_id, resource_name="Team")
    cache_service.mark_domain_data_changed(db)
    await delete_and_flush(db, team)
