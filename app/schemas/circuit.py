from pydantic import BaseModel, Field
from typing import Optional


class CircuitCreate(BaseModel):
    circuit_ref: str = Field(min_length=1, max_length=50, examples=["silverstone"])
    name: str = Field(min_length=1, max_length=100, examples=["Silverstone Circuit"])
    location: Optional[str] = Field(default=None, max_length=100, examples=["Silverstone"])
    country: Optional[str] = Field(default=None, max_length=50, examples=["UK"])
    lat: Optional[float] = Field(default=None, ge=-90, le=90, examples=[52.0786])
    lng: Optional[float] = Field(default=None, ge=-180, le=180, examples=[-1.01694])
    alt: Optional[float] = Field(default=None, examples=[153.0])
    url: Optional[str] = Field(default=None, max_length=255)


class CircuitUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    location: Optional[str] = Field(default=None, max_length=100)
    country: Optional[str] = Field(default=None, max_length=50)
    lat: Optional[float] = Field(default=None, ge=-90, le=90)
    lng: Optional[float] = Field(default=None, ge=-180, le=180)
    alt: Optional[float] = None
    url: Optional[str] = Field(default=None, max_length=255)


class CircuitResponse(BaseModel):
    id: int
    circuit_ref: str
    name: str
    location: Optional[str]
    country: Optional[str]
    lat: Optional[float]
    lng: Optional[float]
    alt: Optional[float]
    url: Optional[str]

    model_config = {"from_attributes": True}
