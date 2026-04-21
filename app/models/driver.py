from sqlalchemy import Integer, String, Date
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional, List
from app.database import Base


class Driver(Base):
    """
    Formula 1 driver.

    Maps to the Ergast dataset's 'drivers.csv' file.
    Key fields mirror the CSV columns exactly so the import script
    can do a direct mapping without transformation.

    Relationships:
    - results: one driver has many race results (one-to-many)
      `back_populates` creates a two-way link:
        driver.results  → list of Result objects
        result.driver   → the Driver object
      `lazy="select"` means results are only fetched when accessed,
      not automatically joined on every driver query.
    """

    __tablename__ = "drivers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Ergast uses a string reference key like "hamilton", "vettel"
    driver_ref: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)

    # driver_number and code can be NULL (historical drivers pre-numbering era)
    driver_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    code: Mapped[Optional[str]] = mapped_column(String(3), nullable=True)  # e.g. "HAM"

    forename: Mapped[str] = mapped_column(String(50), nullable=False)
    surname: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    dob: Mapped[Optional[Date]] = mapped_column(Date, nullable=True)
    nationality: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Relationship to results
    results: Mapped[List["Result"]] = relationship(  # type: ignore[name-defined]
        "Result", back_populates="driver", lazy="select"
    )

    def __repr__(self) -> str:
        return f"<Driver {self.forename} {self.surname} ({self.nationality})>"
