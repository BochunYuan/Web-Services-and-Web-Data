from sqlalchemy import Integer, String, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional, List
from app.database import Base


class Circuit(Base):
    """
    Formula 1 race circuit (track).

    Maps to Ergast 'circuits.csv'.
    Includes geographic coordinates (lat/lng) which enable
    location-based queries and are interesting for visualisation.

    Examples: monza (Italy), silverstone (UK), spa (Belgium)
    """

    __tablename__ = "circuits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    circuit_ref: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    location: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # city
    country: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)

    # Geographic coordinates — useful for analytics/visualisation
    lat: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    lng: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    alt: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # altitude in metres

    url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # One circuit hosts many races over the years
    races: Mapped[List["Race"]] = relationship(  # type: ignore[name-defined]
        "Race", back_populates="circuit", lazy="select"
    )

    def __repr__(self) -> str:
        return f"<Circuit {self.name} ({self.country})>"
