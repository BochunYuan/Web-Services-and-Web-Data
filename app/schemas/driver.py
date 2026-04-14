from pydantic import BaseModel, Field, HttpUrl
from typing import Optional
from datetime import date


class DriverCreate(BaseModel):
    """Fields required when creating a new driver via POST /drivers."""
    driver_ref: str = Field(min_length=1, max_length=50, examples=["hamilton"])
    driver_number: Optional[int] = Field(default=None, ge=1, le=99, examples=[44])
    code: Optional[str] = Field(default=None, min_length=2, max_length=3, examples=["HAM"])
    forename: str = Field(min_length=1, max_length=50, examples=["Lewis"])
    surname: str = Field(min_length=1, max_length=50, examples=["Hamilton"])
    dob: Optional[date] = Field(default=None, examples=["1985-01-07"])
    nationality: Optional[str] = Field(default=None, max_length=50, examples=["British"])
    url: Optional[str] = Field(default=None, max_length=255, examples=["http://en.wikipedia.org/wiki/Lewis_Hamilton"])


class DriverUpdate(BaseModel):
    """
    Fields for updating a driver via PUT /drivers/{id}.
    ALL fields are Optional — client only sends what they want to change.
    This is the standard PATCH-style partial update pattern.
    """
    driver_number: Optional[int] = Field(default=None, ge=1, le=99)
    code: Optional[str] = Field(default=None, min_length=2, max_length=3)
    forename: Optional[str] = Field(default=None, min_length=1, max_length=50)
    surname: Optional[str] = Field(default=None, min_length=1, max_length=50)
    dob: Optional[date] = None
    nationality: Optional[str] = Field(default=None, max_length=50)
    url: Optional[str] = Field(default=None, max_length=255)


class DriverResponse(BaseModel):
    """Driver data returned by the API."""
    id: int
    driver_ref: str
    driver_number: Optional[int]
    code: Optional[str]
    forename: str
    surname: str
    dob: Optional[date]
    nationality: Optional[str]
    url: Optional[str]

    model_config = {"from_attributes": True}
