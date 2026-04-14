from pydantic import BaseModel, Field, model_validator
from typing import Optional, Any
from datetime import date


class CircuitSummary(BaseModel):
    """Inline circuit info embedded in race responses."""
    id: int
    circuit_ref: str
    name: str
    location: Optional[str] = None
    country: Optional[str] = None

    model_config = {"from_attributes": True}


class RaceCreate(BaseModel):
    year: int = Field(ge=1950, le=2100)
    round: int = Field(ge=1, le=30)
    circuit_id: Optional[int] = None
    name: str = Field(min_length=1, max_length=100)
    race_date: Optional[str] = Field(default=None, max_length=20, description="Date in YYYY-MM-DD format")
    race_time: Optional[str] = Field(default=None, max_length=20, description="Time in HH:MM:SS format")
    url: Optional[str] = Field(default=None, max_length=255)


class RaceUpdate(BaseModel):
    circuit_id: Optional[int] = None
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    race_date: Optional[str] = Field(default=None, max_length=20)
    race_time: Optional[str] = Field(default=None, max_length=20)
    url: Optional[str] = Field(default=None, max_length=255)


class RaceResponse(BaseModel):
    id: int
    year: int
    round: int
    circuit_id: Optional[int] = None
    name: str
    # Store date as ISO string to avoid Pydantic v2 date serialization issues
    date: Optional[str] = None
    url: Optional[str] = None
    circuit: Optional[CircuitSummary] = None

    model_config = {"from_attributes": True}

    @model_validator(mode="before")
    @classmethod
    def coerce_date(cls, data: Any) -> Any:
        """Convert datetime.date → ISO string before Pydantic validates the field."""
        # data may be an ORM object (has __dict__) or a plain dict
        if hasattr(data, "__dict__"):
            raw = getattr(data, "date", None)
            if isinstance(raw, date):
                # Return a dict copy so Pydantic can work with it
                d = {c.key: getattr(data, c.key) for c in data.__class__.__table__.columns}
                d["date"] = raw.isoformat()
                d["circuit"] = getattr(data, "circuit", None)
                return d
        elif isinstance(data, dict) and isinstance(data.get("date"), date):
            data = dict(data)
            data["date"] = data["date"].isoformat()
        return data
