from sqlalchemy import Integer, String, Date, Time, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional, List
from app.database import Base


class Race(Base):
    """
    A single Formula 1 race event.

    Maps to Ergast 'races.csv'.
    Each race belongs to a season (year) and a round number within that season,
    and takes place at one circuit.

    The (year, round) pair is unique — there can't be two Round 5s in 2023.
    The circuit_id is a foreign key linking to the circuits table.
    """

    __tablename__ = "races"
    __table_args__ = (
        UniqueConstraint("year", "round", name="uq_races_year_round"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    round: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    date: Mapped[Optional[Date]] = mapped_column(Date, nullable=True)
    time: Mapped[Optional[Time]] = mapped_column(Time, nullable=True)
    url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Foreign key → circuits table
    # ondelete="SET NULL": if a circuit is deleted, races keep existing
    # but circuit_id becomes NULL rather than cascading a delete of all races
    circuit_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("circuits.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Many-to-one: many races held at one circuit
    circuit: Mapped[Optional["Circuit"]] = relationship(  # type: ignore[name-defined]
        "Circuit", back_populates="races", lazy="joined"
        # lazy="joined": circuit info is JOIN-loaded with the race query,
        # because we almost always want to display circuit name alongside race info
    )

    # One race → many results (one per driver entry)
    results: Mapped[List["Result"]] = relationship(  # type: ignore[name-defined]
        "Result", back_populates="race", lazy="select"
    )

    def __repr__(self) -> str:
        return f"<Race {self.year} R{self.round} {self.name}>"
