# Import all models here so that SQLAlchemy's Base.metadata knows about them.
# This is required for create_all() to create all tables in one call.

from app.models.user import User
from app.models.driver import Driver
from app.models.team import Team
from app.models.circuit import Circuit
from app.models.race import Race
from app.models.result import Result

__all__ = ["User", "Driver", "Team", "Circuit", "Race", "Result"]
