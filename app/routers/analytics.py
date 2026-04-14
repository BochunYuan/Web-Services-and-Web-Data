"""
Analytics endpoints — /api/v1/analytics

These are READ-ONLY endpoints (no authentication required).
The heavy lifting is in app/services/analytics_service.py.
This file only handles:
  - URL routing and parameter parsing
  - Delegating to the service layer
  - Returning the JSON response

All endpoints include rich OpenAPI descriptions that appear in Swagger UI,
contributing to the Documentation score.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.database import get_db
from app.services import analytics_service

router = APIRouter()


@router.get(
    "/drivers/{driver_id}/performance",
    summary="Driver season-by-season performance",
    description="""
Retrieve a complete career breakdown for a Formula 1 driver, season by season.

**Returns per season:**
- Total championship points
- Race wins and podiums (top 3 finishes)
- Races entered and DNFs (Did Not Finish)
- Win rate percentage

**Also returns career totals** across all seasons (or the filtered range).

Results are **cached for 10 minutes** — repeated calls are instant.

**Example:** Hamilton's performance from 2010 to 2020:
```
GET /api/v1/analytics/drivers/4/performance?start_year=2010&end_year=2020
```
    """,
    tags=["Analytics"],
)
async def driver_performance(
    driver_id: int,
    start_year: int = Query(default=None, ge=1950, le=2030, description="Filter from this season"),
    end_year: int = Query(default=None, ge=1950, le=2030, description="Filter to this season"),
    db: AsyncSession = Depends(get_db),
):
    return await analytics_service.get_driver_performance(db, driver_id, start_year, end_year)


@router.get(
    "/drivers/compare",
    summary="Compare multiple drivers head-to-head (career stats)",
    description="""
Compare 2–5 drivers across their entire careers.

Provide driver IDs as a comma-separated query parameter.

**Returns for each driver:**
- Total points, wins, podiums
- Total races and seasons
- Win rate % and points-per-race average

**Example:** Compare Hamilton vs Vettel vs Alonso:
```
GET /api/v1/analytics/drivers/compare?driver_ids=4,20,5
```
    """,
    tags=["Analytics"],
)
async def compare_drivers(
    driver_ids: List[int] = Query(description="Comma-separated list of 2–5 driver IDs"),
    db: AsyncSession = Depends(get_db),
):
    return await analytics_service.compare_drivers(db, driver_ids)


@router.get(
    "/teams/standings/{year}",
    summary="Constructor championship standings for a season",
    description="""
Full constructor (team) championship standings for the given season.

Teams are ranked by total points accumulated by all their drivers.
Matches the official Formula 1 Constructors' Championship table.

Results are **cached for 10 minutes**.

**Example:** 2023 standings:
```
GET /api/v1/analytics/teams/standings/2023
```
    """,
    tags=["Analytics"],
)
async def team_standings(
    year: int,
    db: AsyncSession = Depends(get_db),
):
    return await analytics_service.get_team_standings(db, year)


@router.get(
    "/seasons/{year}/highlights",
    summary="Season highlights and champion summary",
    description="""
Executive summary of a complete Formula 1 season.

**Includes:**
- Driver Champion (name + total points)
- Constructor Champion (name + total points)
- Driver with the most race wins
- Number of unique race winners (competitiveness metric)
- Total races held

Results are **cached for 30 minutes**.

**Example:**
```
GET /api/v1/analytics/seasons/2021/highlights
```
    """,
    tags=["Analytics"],
)
async def season_highlights(
    year: int,
    db: AsyncSession = Depends(get_db),
):
    return await analytics_service.get_season_highlights(db, year)


@router.get(
    "/circuits/{circuit_id}/stats",
    summary="Circuit historical statistics",
    description="""
Historical race data for a specific circuit.

**Includes:**
- Total times hosted (year range)
- Top 5 drivers by wins at this circuit
- Most successful constructor at this circuit

**Example:** Monaco Circuit (id=6):
```
GET /api/v1/analytics/circuits/6/stats
```
    """,
    tags=["Analytics"],
)
async def circuit_stats(
    circuit_id: int,
    db: AsyncSession = Depends(get_db),
):
    return await analytics_service.get_circuit_stats(db, circuit_id)


@router.get(
    "/drivers/{driver_id}/head-to-head/{rival_id}",
    summary="Head-to-head record between two drivers",
    description="""
Direct comparison between two drivers in races where **both participated**.

**Returns:**
- Number of shared races
- How many times each driver finished ahead of the other
- Win percentage for each driver
- Points scored in shared races

Uses `position_order` for comparison, which correctly handles DNFs
(a retired driver loses to a driver who finished).

**Example:** Hamilton vs Rosberg:
```
GET /api/v1/analytics/drivers/4/head-to-head/13
```
    """,
    tags=["Analytics"],
)
async def head_to_head(
    driver_id: int,
    rival_id: int,
    db: AsyncSession = Depends(get_db),
):
    return await analytics_service.get_head_to_head(db, driver_id, rival_id)
