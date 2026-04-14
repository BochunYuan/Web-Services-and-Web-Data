from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional, List
from app.database import Base


class Team(Base):
    """
    Formula 1 constructor (team).

    Maps to Ergast 'constructors.csv'.
    In F1 terminology, "constructor" is the official term for a team
    (the entity that builds and enters the car). We name the table
    "teams" for clarity in the API, but keep 'constructor_ref' to
    stay consistent with the dataset.

    Examples: ferrari, mercedes, red_bull, mclaren
    """

    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    constructor_ref: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    nationality: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # One team → many results
    results: Mapped[List["Result"]] = relationship(  # type: ignore[name-defined]
        "Result", back_populates="team", lazy="select"
    )

    def __repr__(self) -> str:
        return f"<Team {self.name} ({self.nationality})>"
