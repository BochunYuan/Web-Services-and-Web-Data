from pydantic import BaseModel, Field, model_validator
from typing import Optional, Any
from datetime import date, time


class CircuitSummary(BaseModel):
    """Inline circuit info embedded in race responses."""
    id: int
    circuit_ref: str
    name: str
    location: Optional[str] = None
    country: Optional[str] = None

    model_config = {"from_attributes": True}


class RaceCreate(BaseModel):
    year: int = Field(ge=1950, le=2100, examples=[2027])
    round: int = Field(ge=1, le=30, examples=[25])
    circuit_id: Optional[int] = Field(default=None, examples=[None])
    name: str = Field(min_length=1, max_length=100, examples=["Demo Harbour Grand Prix"])
    race_date: Optional[date] = Field(default=None, description="Date in YYYY-MM-DD format", examples=["2027-11-20"])
    race_time: Optional[time] = Field(default=None, description="Time in HH:MM:SS format", examples=["20:00:00"])
    url: Optional[str] = Field(default=None, max_length=255, examples=["https://example.com/races/demo-harbour-grand-prix"])


class RaceUpdate(BaseModel):
    circuit_id: Optional[int] = None
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    race_date: Optional[date] = Field(default=None)
    race_time: Optional[time] = Field(default=None)
    url: Optional[str] = Field(default=None, max_length=255)


class RaceResponse(BaseModel):
    id: int
    year: int
    round: int
    circuit_id: Optional[int] = None
    name: str
    # Store date as ISO string to avoid Pydantic v2 date serialization issues
    date: Optional[str] = None
    time: Optional[str] = None
    url: Optional[str] = None
    circuit: Optional[CircuitSummary] = None

    model_config = {"from_attributes": True}

    @model_validator(mode="before")
    @classmethod
    def coerce_date(cls, data: Any) -> Any:
        """Convert date/time objects to ISO strings before Pydantic validates."""
        # data may be an ORM object (has __dict__) or a plain dict
        if hasattr(data, "__dict__"):
            raw_date = getattr(data, "date", None)
            raw_time = getattr(data, "time", None)
            if isinstance(raw_date, date) or isinstance(raw_time, time):
                # Return a dict copy so Pydantic can work with it
                d = {c.key: getattr(data, c.key) for c in data.__class__.__table__.columns}
                if isinstance(raw_date, date):
                    d["date"] = raw_date.isoformat()
                if isinstance(raw_time, time):
                    d["time"] = raw_time.isoformat()
                d["circuit"] = getattr(data, "circuit", None)
                return d
        elif isinstance(data, dict):
            raw_date = data.get("date")
            raw_time = data.get("time")
            if isinstance(raw_date, date) or isinstance(raw_time, time):
                data = dict(data)
                if isinstance(raw_date, date):
                    data["date"] = raw_date.isoformat()
                if isinstance(raw_time, time):
                    data["time"] = raw_time.isoformat()
        return data
