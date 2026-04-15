from pydantic import BaseModel
from typing import Optional, List, Union


class AnalyticsDriverSummary(BaseModel):
    id: int
    name: str
    nationality: Optional[str] = None
    code: Optional[str] = None


class DriverSeasonPerformance(BaseModel):
    year: int
    total_points: float
    wins: int
    podiums: int
    races_entered: int
    dnfs: int
    win_rate: float


class DriverCareerSummary(BaseModel):
    total_seasons: int
    total_points: float
    total_wins: int
    total_podiums: int
    total_races: int


class DriverPerformanceResponse(BaseModel):
    driver: AnalyticsDriverSummary
    seasons: List[DriverSeasonPerformance]
    career_summary: DriverCareerSummary


class DriverComparisonStats(BaseModel):
    total_points: float
    wins: int
    podiums: int
    races_entered: int
    dnfs: int
    seasons: int
    win_rate_pct: float
    points_per_race: float


class DriverComparisonEntry(BaseModel):
    driver: AnalyticsDriverSummary
    stats: DriverComparisonStats


class DriverComparisonResponse(BaseModel):
    drivers_compared: int
    comparisons: List[DriverComparisonEntry]


class TeamStandingEntry(BaseModel):
    position: int
    team_id: int
    team_name: str
    nationality: Optional[str] = None
    total_points: float
    wins: int
    race_entries: int
    drivers_used: int


class TeamStandingsResponse(BaseModel):
    season: int
    total_races: int
    standings: List[TeamStandingEntry]


class SeasonChampionSummary(BaseModel):
    id: int
    name: str
    points: float


class MostRaceWinsSummary(BaseModel):
    driver: str
    wins: int


class SeasonHighlightsResponse(BaseModel):
    season: int
    total_races: int
    champion_driver: Optional[SeasonChampionSummary] = None
    champion_constructor: Optional[SeasonChampionSummary] = None
    most_race_wins: Optional[MostRaceWinsSummary] = None
    unique_race_winners: int
    total_points_scored: float


class CircuitStatsCircuitSummary(BaseModel):
    id: int
    name: str
    location: Optional[str] = None
    country: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None


class CircuitWinnerEntry(BaseModel):
    driver: str
    wins: int


class CircuitConstructorSummary(BaseModel):
    name: str
    wins: int
    total_points: float


class CircuitStatsResponse(BaseModel):
    circuit: CircuitStatsCircuitSummary
    total_races_hosted: int
    first_race_year: int
    last_race_year: int
    top_winners: List[CircuitWinnerEntry]
    most_successful_constructor: Optional[CircuitConstructorSummary] = None


class CircuitNoDataResponse(BaseModel):
    circuit: CircuitStatsCircuitSummary
    total_races_hosted: int
    message: str


class HeadToHeadDriverSummary(BaseModel):
    id: int
    name: str
    nationality: Optional[str] = None


class HeadToHeadStats(BaseModel):
    driver_wins: int
    rival_wins: int
    ties: int
    driver_win_pct: float
    rival_win_pct: float


class HeadToHeadPointsSummary(BaseModel):
    driver_points: float
    rival_points: float


class HeadToHeadResponse(BaseModel):
    driver: HeadToHeadDriverSummary
    rival: HeadToHeadDriverSummary
    shared_races: int
    head_to_head: HeadToHeadStats
    points_in_shared_races: HeadToHeadPointsSummary


class HeadToHeadNoSharedRacesResponse(BaseModel):
    driver: HeadToHeadDriverSummary
    rival: HeadToHeadDriverSummary
    shared_races: int
    message: str


CircuitStatsResult = Union[CircuitStatsResponse, CircuitNoDataResponse]
HeadToHeadResult = Union[HeadToHeadResponse, HeadToHeadNoSharedRacesResponse]
