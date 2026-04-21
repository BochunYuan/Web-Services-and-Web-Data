"""
Reusable SQLAlchemy expressions for analytics aggregation queries.

These helpers keep the business queries readable while centralising the
definition of common F1 statistics such as wins, podiums, DNFs, and points.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import and_, case, distinct, func

from app.models.race import Race
from app.models.result import Result


def count_if(condition: Any) -> Any:
    """Count rows where a SQL condition is true."""
    return func.count(case((condition, 1)))


def total_points(result_model: Any = Result) -> Any:
    """Sum points scored by result rows."""
    return func.sum(result_model.points)


def result_count(result_model: Any = Result) -> Any:
    """Count result rows."""
    return func.count(result_model.id)


def win_count(result_model: Any = Result) -> Any:
    """Count race wins within an unfiltered result set."""
    return count_if(result_model.position == 1)


def podium_count(result_model: Any = Result) -> Any:
    """Count podium finishes within an unfiltered result set."""
    return count_if(result_model.position <= 3)


def dnf_count(result_model: Any = Result) -> Any:
    """Count non-finished races where no classified position exists."""
    return count_if(and_(result_model.position.is_(None), result_model.status != "Finished"))


def distinct_driver_count(result_model: Any = Result) -> Any:
    """Count distinct drivers represented by result rows."""
    return func.count(distinct(result_model.driver_id))


def distinct_season_count(race_model: Any = Race) -> Any:
    """Count distinct seasons represented by joined race rows."""
    return func.count(distinct(race_model.year))


def driver_result_summary_columns(
    *,
    result_model: Any = Result,
    race_model: Any = Race,
    include_seasons: bool = False,
) -> list[Any]:
    """Shared aggregate columns for driver performance and comparison queries."""
    columns = [
        total_points(result_model).label("total_points"),
        win_count(result_model).label("wins"),
        podium_count(result_model).label("podiums"),
        result_count(result_model).label("races_entered"),
        dnf_count(result_model).label("dnfs"),
    ]
    if include_seasons:
        columns.append(distinct_season_count(race_model).label("seasons"))
    return columns
