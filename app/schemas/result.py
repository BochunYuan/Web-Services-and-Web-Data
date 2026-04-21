from pydantic import BaseModel
from typing import Optional


class ResultResponse(BaseModel):
    """
    Result is read-only (imported from CSV), so we only need a response schema.
    No Create/Update schemas needed.
    """
    id: int
    race_id: int
    driver_id: int
    constructor_id: Optional[int]
    grid: Optional[int]
    position: Optional[int]
    position_text: Optional[str]
    points: float
    laps: Optional[int]
    time_text: Optional[str]
    fastest_lap_time: Optional[str]
    fastest_lap_speed: Optional[float]
    status: Optional[str]

    model_config = {"from_attributes": True}
