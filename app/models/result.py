from sqlalchemy import Integer, String, Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional
from app.database import Base


class Result(Base):
    """
    Race result — one row per driver per race.

    Maps to Ergast 'results.csv'. This is the central fact table
    linking drivers, teams, and races together (star schema pattern).

    This model is READ-ONLY via the API — data comes from the CSV import.
    Analytics queries are built on top of this table (aggregating points,
    counting wins, calculating DNF rates, etc.).

    Key fields explained:
    - grid:        starting grid position (1 = pole position)
    - position:    finishing position (NULL if DNF/DNS)
    - position_text: "1", "2", "R" (retired), "D" (disqualified), "W" (withdrew)
    - points:      championship points awarded (varies by era)
    - laps:        number of laps completed
    - status:      "Finished", "Engine", "Accident", "Collision", etc.
    - fastest_lap_time: e.g. "1:18.739"
    - fastest_lap_speed: average speed in km/h for the fastest lap
    """

    __tablename__ = "results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Foreign keys — the three dimensions of this fact table
    race_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("races.id", ondelete="CASCADE"), nullable=False, index=True
    )
    driver_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("drivers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    constructor_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("teams.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Race-day data
    grid: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    position: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    position_text: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)
    position_order: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    points: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    laps: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    time_text: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # race finish time
    milliseconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    fastest_lap: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # lap number
    fastest_lap_time: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    fastest_lap_speed: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)

    # Relationships (back-populate to the three dimension tables)
    race: Mapped["Race"] = relationship("Race", back_populates="results", lazy="joined")
    driver: Mapped["Driver"] = relationship("Driver", back_populates="results", lazy="select")
    team: Mapped[Optional["Team"]] = relationship("Team", back_populates="results", lazy="select")

    def __repr__(self) -> str:
        return f"<Result race={self.race_id} driver={self.driver_id} pos={self.position}>"
