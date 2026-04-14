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
from app.utils.pagination import PaginationParams, PagedResponse
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
    team = (await db.execute(select(Team).where(Team.id == team_id))).scalar_one_or_none()
    if team is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Team {team_id} not found")
    return team


@router.post(
    "",
    response_model=TeamResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new team",
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
    db.add(team)
    await db.commit()
    await db.refresh(team)
    return team


@router.put("/{team_id}", response_model=TeamResponse, summary="Update a team")
async def update_team(
    team_id: int,
    data: TeamUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> TeamResponse:
    team = (await db.execute(select(Team).where(Team.id == team_id))).scalar_one_or_none()
    if team is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Team {team_id} not found")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(team, field, value)

    await db.commit()
    await db.refresh(team)
    return team


@router.delete("/{team_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a team")
async def delete_team(
    team_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> None:
    team = (await db.execute(select(Team).where(Team.id == team_id))).scalar_one_or_none()
    if team is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Team {team_id} not found")
    await db.delete(team)
    await db.commit()
