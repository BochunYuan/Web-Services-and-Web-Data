from pydantic import BaseModel, Field
from typing import Optional


class TeamCreate(BaseModel):
    constructor_ref: str = Field(min_length=1, max_length=50, examples=["mercedes"])
    name: str = Field(min_length=1, max_length=100, examples=["Mercedes"])
    nationality: Optional[str] = Field(default=None, max_length=50, examples=["German"])
    url: Optional[str] = Field(default=None, max_length=255)


class TeamUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    nationality: Optional[str] = Field(default=None, max_length=50)
    url: Optional[str] = Field(default=None, max_length=255)


class TeamResponse(BaseModel):
    id: int
    constructor_ref: str
    name: str
    nationality: Optional[str]
    url: Optional[str]

    model_config = {"from_attributes": True}
