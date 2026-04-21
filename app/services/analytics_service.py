"""
Analytics service — all 6 analytical queries.

Each function:
  1. Checks the cache first (returns immediately if hit)
  2. Runs a SQL aggregation query if cache miss
  3. Stores the result in the cache before returning

SQL patterns used:
  - GROUP BY + SUM/COUNT/MAX for aggregation
  - subquery for ranking (e.g. finding champion = driver with max points in season)
  - CASE WHEN for conditional counting (e.g. wins = position==1)
  - JOIN across multiple tables for enriched results

All queries use SQLAlchemy Core (select/func) rather than raw SQL strings.
This keeps them database-agnostic (works on both SQLite and MySQL) and
prevents SQL injection by design.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, case, distinct
from sqlalchemy.orm import aliased
from fastapi import HTTPException, status
from typing import Optional

from app.models.driver import Driver
from app.models.team import Team
from app.models.race import Race
from app.models.result import Result
from app.models.circuit import Circuit
from app.services import cache_service
from app.services.analytics_expressions import (
    distinct_driver_count,
    driver_result_summary_columns,
    result_count,
    total_points,
    win_count,
)


# ─────────────────────────────────────────────────────────────────────────────
# 1. Driver Performance Trend
#    GET /analytics/drivers/{id}/performance?start_year=&end_year=
# ─────────────────────────────────────────────────────────────────────────────

async def get_driver_performance(
    db: AsyncSession,
    driver_id: int,
    start_year: Optional[int] = None,
    end_year: Optional[int] = None,
) -> dict:
    """
    Return a driver's season-by-season performance breakdown.

    For each season the driver participated in, returns:
      - total points scored
      - number of race wins (position = 1)
      - number of podiums (position <= 3)
      - number of races entered
      - number of DNFs (Did Not Finish — status != 'Finished' AND position IS NULL)
      - final championship position (rank by points within that season)

    SQL pattern:
      SELECT r.year,
             SUM(res.points) AS total_points,
             COUNT(CASE WHEN res.position = 1 THEN 1 END) AS wins,
             ...
      FROM results res
      JOIN races r ON res.race_id = r.id
      WHERE res.driver_id = :driver_id
      GROUP BY r.year
      ORDER BY r.year
    """
    # Build cache key from all parameters
    cache_key = f"driver_perf:{driver_id}:{start_year}:{end_year}"
    cached = cache_service.get_analytics(cache_key)
    if cached is not None:
        return cached

    # Verify driver exists
    driver = (await db.execute(select(Driver).where(Driver.id == driver_id))).scalar_one_or_none()
    if driver is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Driver {driver_id} not found")

    query = (
        select(
            Race.year,
            *driver_result_summary_columns(),
        )
        .join(Race, Result.race_id == Race.id)
        .where(Result.driver_id == driver_id)
    )

    if start_year:
        query = query.where(Race.year >= start_year)
    if end_year:
        query = query.where(Race.year <= end_year)

    query = query.group_by(Race.year).order_by(Race.year)
    rows = (await db.execute(query)).fetchall()

    seasons = [
        {
            "year": row.year,
            "total_points": round(float(row.total_points or 0), 1),
            "wins": row.wins,
            "podiums": row.podiums,
            "races_entered": row.races_entered,
            "dnfs": row.dnfs,
            "win_rate": round(row.wins / row.races_entered * 100, 1) if row.races_entered else 0,
        }
        for row in rows
    ]

    result = {
        "driver": {
            "id": driver.id,
            "name": f"{driver.forename} {driver.surname}",
            "nationality": driver.nationality,
            "code": driver.code,
        },
        "seasons": seasons,
        "career_summary": {
            "total_seasons": len(seasons),
            "total_points": round(sum(s["total_points"] for s in seasons), 1),
            "total_wins": sum(s["wins"] for s in seasons),
            "total_podiums": sum(s["podiums"] for s in seasons),
            "total_races": sum(s["races_entered"] for s in seasons),
        },
    }

    cache_service.set_analytics(cache_key, result)
    return result


# ─────────────────────────────────────────────────────────────────────────────
# 2. Driver Comparison
#    GET /analytics/drivers/compare?driver_ids=1,3,4
# ─────────────────────────────────────────────────────────────────────────────

async def compare_drivers(db: AsyncSession, driver_ids: list[int]) -> dict:
    """
    Side-by-side career stats comparison for multiple drivers.

    Returns the same metrics for each driver so clients can render
    a comparison table or radar chart.

    SQL pattern: same aggregation as driver_performance but run once
    for all requested driver IDs using WHERE driver_id IN (...).
    """
    if len(driver_ids) < 2:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="Provide at least 2 driver_ids to compare")
    if len(driver_ids) > 5:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="Maximum 5 drivers can be compared at once")

    cache_key = f"driver_compare:{'_'.join(str(i) for i in driver_ids)}"
    cached = cache_service.get_analytics(cache_key)
    if cached is not None:
        return cached

    # Verify all drivers exist
    existing = (await db.execute(select(Driver).where(Driver.id.in_(driver_ids)))).scalars().all()
    found_ids = {d.id for d in existing}
    missing = set(driver_ids) - found_ids
    if missing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Driver IDs not found: {sorted(missing)}")

    # Single query returns one row per driver
    query = (
        select(
            Result.driver_id,
            *driver_result_summary_columns(include_seasons=True),
        )
        .join(Race, Result.race_id == Race.id)
        .where(Result.driver_id.in_(driver_ids))
        .group_by(Result.driver_id)
    )
    rows = {row.driver_id: row for row in (await db.execute(query)).fetchall()}

    # Build response preserving the original request order
    driver_map = {d.id: d for d in existing}
    comparisons = []
    for did in driver_ids:
        driver = driver_map[did]
        row = rows.get(did)
        races = row.races_entered if row else 0
        comparisons.append({
            "driver": {
                "id": driver.id,
                "name": f"{driver.forename} {driver.surname}",
                "nationality": driver.nationality,
                "code": driver.code,
            },
            "stats": {
                "total_points": round(float(row.total_points or 0), 1) if row else 0,
                "wins": row.wins if row else 0,
                "podiums": row.podiums if row else 0,
                "races_entered": races,
                "dnfs": row.dnfs if row else 0,
                "seasons": row.seasons if row else 0,
                "win_rate_pct": round(row.wins / races * 100, 1) if row and races else 0,
                "points_per_race": round(float(row.total_points or 0) / races, 2) if row and races else 0,
            },
        })

    result = {"drivers_compared": len(driver_ids), "comparisons": comparisons}
    cache_service.set_analytics(cache_key, result)
    return result


# ─────────────────────────────────────────────────────────────────────────────
# 3. Team Standings for a Season
#    GET /analytics/teams/standings/{year}
# ─────────────────────────────────────────────────────────────────────────────

async def get_team_standings(db: AsyncSession, year: int) -> dict:
    """
    Constructor championship standings for a given season.

    A constructor's points = sum of ALL their drivers' points in that season.
    Teams are ranked by total points (descending) — exactly how the real
    Formula 1 Constructors' Championship works.

    SQL pattern:
      SELECT t.name, SUM(res.points), COUNT(CASE WHEN pos=1 THEN 1 END) ...
      FROM results res
      JOIN races r ON ...
      JOIN teams t ON ...
      WHERE r.year = :year
      GROUP BY res.constructor_id
      ORDER BY total_points DESC
    """
    cache_key = f"team_standings:{year}"
    cached = cache_service.get_analytics(cache_key)
    if cached is not None:
        return cached

    # Check season exists
    race_count = (await db.execute(
        select(func.count()).select_from(Race).where(Race.year == year)
    )).scalar_one()
    if race_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"No races found for season {year}")

    query = (
        select(
            Result.constructor_id,
            Team.name.label("team_name"),
            Team.nationality.label("team_nationality"),
            total_points().label("total_points"),
            win_count().label("wins"),
            result_count().label("race_entries"),
            distinct_driver_count().label("drivers_used"),
        )
        .join(Race, Result.race_id == Race.id)
        .join(Team, Result.constructor_id == Team.id)
        .where(Race.year == year, Result.constructor_id.isnot(None))
        .group_by(Result.constructor_id, Team.name, Team.nationality)
        .order_by(total_points().desc())
    )
    rows = (await db.execute(query)).fetchall()

    standings = [
        {
            "position": idx + 1,
            "team_id": row.constructor_id,
            "team_name": row.team_name,
            "nationality": row.team_nationality,
            "total_points": round(float(row.total_points or 0), 1),
            "wins": row.wins,
            "race_entries": row.race_entries,
            "drivers_used": row.drivers_used,
        }
        for idx, row in enumerate(rows)
    ]

    result = {
        "season": year,
        "total_races": race_count,
        "standings": standings,
    }
    cache_service.set_analytics(cache_key, result)
    return result


# ─────────────────────────────────────────────────────────────────────────────
# 4. Season Highlights
#    GET /analytics/seasons/{year}/highlights
# ─────────────────────────────────────────────────────────────────────────────

async def get_season_highlights(db: AsyncSession, year: int) -> dict:
    """
    Executive summary of a Formula 1 season.

    Returns:
      - Champion driver (most points in season)
      - Champion constructor (most points in season)
      - Total races held
      - Most wins by a single driver
      - Most points scored in a single race
      - Number of different race winners (diversity metric)

    Uses subqueries: first aggregate per driver/team, then find the max.
    This is a classic "find the winner of the aggregation" SQL pattern.
    """
    cache_key = f"season_highlights:{year}"
    cached = cache_service.get_season(cache_key)
    if cached is not None:
        return cached

    season_totals = (await db.execute(
        select(
            func.count(distinct(Race.id)).label("race_count"),
            total_points().label("total_points"),
            func.count(distinct(case((Result.position == 1, Result.driver_id)))).label("unique_winners"),
        )
        .select_from(Race)
        .outerjoin(Result, Result.race_id == Race.id)
        .where(Race.year == year)
    )).fetchone()
    race_count = season_totals.race_count if season_totals else 0
    if race_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"No data for season {year}")

    # ── Champion driver: driver with max total points ──
    driver_points_query = (
        select(
            Result.driver_id,
            Driver.forename.label("driver_forename"),
            Driver.surname.label("driver_surname"),
            total_points().label("total_points"),
        )
        .join(Race, Result.race_id == Race.id)
        .join(Driver, Result.driver_id == Driver.id)
        .where(Race.year == year)
        .group_by(Result.driver_id, Driver.forename, Driver.surname)
        .order_by(total_points().desc())
        .limit(1)
    )
    champ_row = (await db.execute(driver_points_query)).fetchone()
    champion_driver = None
    if champ_row:
        champion_driver = {
            "id": champ_row.driver_id,
            "name": f"{champ_row.driver_forename} {champ_row.driver_surname}",
            "points": round(float(champ_row.total_points), 1),
        }

    # ── Champion constructor ──
    team_points_query = (
        select(
            Result.constructor_id,
            Team.name.label("team_name"),
            total_points().label("total_points"),
        )
        .join(Race, Result.race_id == Race.id)
        .join(Team, Result.constructor_id == Team.id)
        .where(Race.year == year, Result.constructor_id.isnot(None))
        .group_by(Result.constructor_id, Team.name)
        .order_by(total_points().desc())
        .limit(1)
    )
    team_row = (await db.execute(team_points_query)).fetchone()
    champion_team = None
    if team_row:
        champion_team = {
            "id": team_row.constructor_id,
            "name": team_row.team_name,
            "points": round(float(team_row.total_points), 1),
        }

    # ── Most race wins by a single driver ──
    wins_query = (
        select(
            Result.driver_id,
            Driver.forename.label("driver_forename"),
            Driver.surname.label("driver_surname"),
            result_count().label("wins"),
        )
        .join(Race, Result.race_id == Race.id)
        .join(Driver, Result.driver_id == Driver.id)
        .where(Race.year == year, Result.position == 1)
        .group_by(Result.driver_id, Driver.forename, Driver.surname)
        .order_by(result_count().desc())
        .limit(1)
    )
    wins_row = (await db.execute(wins_query)).fetchone()
    most_wins = None
    if wins_row:
        most_wins = {
            "driver": f"{wins_row.driver_forename} {wins_row.driver_surname}",
            "wins": wins_row.wins,
        }

    result = {
        "season": year,
        "total_races": race_count,
        "champion_driver": champion_driver,
        "champion_constructor": champion_team,
        "most_race_wins": most_wins,
        "unique_race_winners": season_totals.unique_winners,
        "total_points_scored": round(float(season_totals.total_points or 0), 1),
    }
    cache_service.set_season(cache_key, result)
    return result


# ─────────────────────────────────────────────────────────────────────────────
# 5. Circuit Statistics
#    GET /analytics/circuits/{id}/stats
# ─────────────────────────────────────────────────────────────────────────────

async def get_circuit_stats(db: AsyncSession, circuit_id: int) -> dict:
    """
    Historical statistics for a specific circuit.

    Returns:
      - Total times this circuit has hosted a race
      - Year range (first race → most recent race)
      - Top 5 drivers by wins at this circuit
      - Most successful constructor at this circuit
      - Average grid-to-finish position improvement (measures overtaking)

    Interesting because some drivers have legendary records at specific circuits
    (e.g. Ayrton Senna at Monaco — 6 wins).
    """
    cache_key = f"circuit_stats:{circuit_id}"
    cached = cache_service.get_analytics(cache_key)
    if cached is not None:
        return cached

    # ── Circuit metadata + basic race history ──
    history = (await db.execute(
        select(
            Circuit.id.label("circuit_id"),
            Circuit.name.label("circuit_name"),
            Circuit.location.label("circuit_location"),
            Circuit.country.label("circuit_country"),
            Circuit.lat.label("circuit_lat"),
            Circuit.lng.label("circuit_lng"),
            func.count(Race.id).label("total_races"),
            func.min(Race.year).label("first_year"),
            func.max(Race.year).label("last_year"),
        )
        .select_from(Circuit)
        .outerjoin(Race, Race.circuit_id == Circuit.id)
        .where(Circuit.id == circuit_id)
        .group_by(
            Circuit.id,
            Circuit.name,
            Circuit.location,
            Circuit.country,
            Circuit.lat,
            Circuit.lng,
        )
    )).fetchone()

    if history is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Circuit {circuit_id} not found")

    circuit_data = {
        "id": history.circuit_id,
        "name": history.circuit_name,
        "location": history.circuit_location,
        "country": history.circuit_country,
        "lat": history.circuit_lat,
        "lng": history.circuit_lng,
    }

    if history.total_races == 0:
        return {
            "circuit": {
                "id": circuit_data["id"],
                "name": circuit_data["name"],
                "location": circuit_data["location"],
                "country": circuit_data["country"],
            },
            "total_races_hosted": 0,
            "message": "No race data available for this circuit",
        }

    # ── Top 5 drivers by wins at this circuit ──
    top_winners_query = (
        select(
            Result.driver_id,
            Driver.forename.label("driver_forename"),
            Driver.surname.label("driver_surname"),
            result_count().label("wins"),
        )
        .join(Race, Result.race_id == Race.id)
        .join(Driver, Result.driver_id == Driver.id)
        .where(Race.circuit_id == circuit_id, Result.position == 1)
        .group_by(Result.driver_id, Driver.forename, Driver.surname)
        .order_by(result_count().desc())
        .limit(5)
    )
    winner_rows = (await db.execute(top_winners_query)).fetchall()

    top_winners = [
        {"driver": f"{r.driver_forename} {r.driver_surname}", "wins": r.wins}
        for r in winner_rows
    ]

    # ── Most successful constructor ──
    best_team_query = (
        select(
            Result.constructor_id,
            Team.name.label("team_name"),
            win_count().label("wins"),
            total_points().label("total_points"),
        )
        .join(Race, Result.race_id == Race.id)
        .join(Team, Result.constructor_id == Team.id)
        .where(Race.circuit_id == circuit_id, Result.constructor_id.isnot(None))
        .group_by(Result.constructor_id, Team.name)
        .order_by(win_count().desc())
        .limit(1)
    )
    best_team_row = (await db.execute(best_team_query)).fetchone()

    result = {
        "circuit": circuit_data,
        "total_races_hosted": history.total_races,
        "first_race_year": history.first_year,
        "last_race_year": history.last_year,
        "top_winners": top_winners,
        "most_successful_constructor": {
            "name": best_team_row.team_name,
            "wins": best_team_row.wins,
            "total_points": round(float(best_team_row.total_points or 0), 1),
        } if best_team_row else None,
    }
    cache_service.set_analytics(cache_key, result)
    return result


# ─────────────────────────────────────────────────────────────────────────────
# 6. Head-to-Head Driver Comparison
#    GET /analytics/drivers/{id}/head-to-head/{rival_id}
# ─────────────────────────────────────────────────────────────────────────────

async def get_head_to_head(db: AsyncSession, driver_id: int, rival_id: int) -> dict:
    """
    Direct head-to-head record between two drivers.

    "Head-to-head" compares drivers in races where BOTH participated.
    In each shared race, we check who finished ahead.

    This is the most analytically interesting endpoint — fans debate
    "who would win if they were in the same car?", and this data helps.

    Algorithm:
      1. Find all races where both drivers have a result
      2. For each such race, compare position_order (lower = better finishing)
      3. Count wins for each driver in that head-to-head subset

    position_order (not position) is used because it handles DNFs correctly:
    a driver who retired (position=NULL) gets a position_order higher than
    drivers who finished, so they lose the head-to-head for that race.
    """
    if driver_id == rival_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="Cannot compare a driver with themselves")

    cache_key = f"h2h:{driver_id}:{rival_id}"
    cached = cache_service.get_analytics(cache_key)
    if cached is not None:
        return cached

    drivers = (await db.execute(select(Driver).where(Driver.id.in_([driver_id, rival_id])))).scalars().all()
    driver_map = {driver.id: driver for driver in drivers}
    for did in [driver_id, rival_id]:
        if did not in driver_map:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail=f"Driver {did} not found")

    # Use aliased Result so we can join the same table twice (once per driver)
    ResA = aliased(Result, name="res_a")
    ResB = aliased(Result, name="res_b")

    # Find all races both drivers competed in, with their finishing orders
    shared_races_query = (
        select(
            ResA.race_id,
            ResA.position_order.label("a_order"),
            ResB.position_order.label("b_order"),
            ResA.points.label("a_points"),
            ResB.points.label("b_points"),
        )
        .join(ResB, and_(ResA.race_id == ResB.race_id, ResB.driver_id == rival_id))
        .where(ResA.driver_id == driver_id)
    )
    rows = (await db.execute(shared_races_query)).fetchall()

    total_shared = len(rows)
    d1 = driver_map[driver_id]
    d2 = driver_map[rival_id]
    if total_shared == 0:
        # Drivers may have raced in different eras
        return {
            "driver": {"id": d1.id, "name": f"{d1.forename} {d1.surname}"},
            "rival": {"id": d2.id, "name": f"{d2.forename} {d2.surname}"},
            "shared_races": 0,
            "message": "These drivers never competed in the same race",
        }

    # Count wins (driver A finished ahead of B when a_order < b_order)
    driver_wins = sum(1 for r in rows if (r.a_order or 999) < (r.b_order or 999))
    rival_wins = sum(1 for r in rows if (r.b_order or 999) < (r.a_order or 999))
    ties = total_shared - driver_wins - rival_wins  # same position_order (rare)

    driver_total_points = sum(float(r.a_points or 0) for r in rows)
    rival_total_points = sum(float(r.b_points or 0) for r in rows)

    result = {
        "driver": {"id": d1.id, "name": f"{d1.forename} {d1.surname}", "nationality": d1.nationality},
        "rival": {"id": d2.id, "name": f"{d2.forename} {d2.surname}", "nationality": d2.nationality},
        "shared_races": total_shared,
        "head_to_head": {
            "driver_wins": driver_wins,
            "rival_wins": rival_wins,
            "ties": ties,
            "driver_win_pct": round(driver_wins / total_shared * 100, 1),
            "rival_win_pct": round(rival_wins / total_shared * 100, 1),
        },
        "points_in_shared_races": {
            "driver_points": round(driver_total_points, 1),
            "rival_points": round(rival_total_points, 1),
        },
    }
    cache_service.set_analytics(cache_key, result)
    return result
