"""
Circuit CRUD endpoints — /api/v1/circuits
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional

from app.database import get_db
from app.models.circuit import Circuit
from app.schemas.circuit import CircuitCreate, CircuitUpdate, CircuitResponse
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
    response_model=PagedResponse[CircuitResponse],
    summary="List all circuits",
    description="Paginated list of F1 circuits. Filter by `country` or search by circuit `name`.",
)
async def list_circuits(
    pagination: PaginationParams = Depends(),
    country: Optional[str] = Query(default=None, description="Filter by country"),
    search: Optional[str] = Query(default=None, description="Search by circuit name"),
    db: AsyncSession = Depends(get_db),
) -> PagedResponse[CircuitResponse]:
    query = select(Circuit)
    count_query = select(func.count()).select_from(Circuit)

    if country:
        query = query.where(Circuit.country.ilike(f"%{country}%"))
        count_query = count_query.where(Circuit.country.ilike(f"%{country}%"))
    if search:
        query = query.where(Circuit.name.ilike(f"%{search}%"))
        count_query = count_query.where(Circuit.name.ilike(f"%{search}%"))

    total = (await db.execute(count_query)).scalar_one()
    query = query.order_by(Circuit.name).offset(pagination.offset).limit(pagination.limit)
    circuits = (await db.execute(query)).scalars().all()

    return PagedResponse.create(items=list(circuits), total=total, pagination=pagination)


@router.get("/{circuit_id}", response_model=CircuitResponse, summary="Get a circuit by ID")
async def get_circuit(circuit_id: int, db: AsyncSession = Depends(get_db)) -> CircuitResponse:
    return await get_or_404(db, Circuit, circuit_id, resource_name="Circuit")


@router.post(
    "",
    response_model=CircuitResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new circuit",
    description="""
Requires authentication. Creates a new circuit row and leaves the imported historical
circuits unchanged unless you explicitly call `PUT /api/v1/circuits/{circuit_id}`.
    """,
)
async def create_circuit(
    data: CircuitCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> CircuitResponse:
    existing = (await db.execute(select(Circuit).where(Circuit.circuit_ref == data.circuit_ref))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"circuit_ref '{data.circuit_ref}' already exists")

    circuit = Circuit(**data.model_dump())
    cache_service.mark_domain_data_changed(db)
    return await add_flush_refresh_or_409(
        db,
        circuit,
        conflict_detail=f"circuit_ref '{data.circuit_ref}' already exists",
    )


@router.put("/{circuit_id}", response_model=CircuitResponse, summary="Update a circuit")
async def update_circuit(
    circuit_id: int,
    data: CircuitUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> CircuitResponse:
    circuit = await get_or_404(db, Circuit, circuit_id, resource_name="Circuit")

    apply_partial_update(circuit, data)
    cache_service.mark_domain_data_changed(db)

    return await flush_and_refresh(db, circuit)


@router.delete("/{circuit_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a circuit")
async def delete_circuit(
    circuit_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> None:
    circuit = await get_or_404(db, Circuit, circuit_id, resource_name="Circuit")
    cache_service.mark_domain_data_changed(db)
    await delete_and_flush(db, circuit)
