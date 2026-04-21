from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from typing import List

from app.database_urls import to_async_database_url


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables / .env file.

    Using pydantic-settings means:
    1. All values are type-validated automatically
    2. Values come from .env file or real environment variables
    3. If a required value is missing, the app fails loudly at startup
       (not silently mid-request)
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Environment
    ENVIRONMENT: str = "development"

    # Security
    # Development gets a safe default so the bundled demo database can be run
    # straight from a fresh clone. Production should always override this.
    SECRET_KEY: str = "dev-insecure-change-me"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./f1_analytics.db"

    # API metadata
    API_V1_PREFIX: str = "/api/v1"
    PROJECT_NAME: str = "F1 Analytics API"
    PROJECT_VERSION: str = "1.0.0"
    PROJECT_DESCRIPTION: str = (
        "A RESTful API for Formula 1 World Championship data analysis. "
        "Provides CRUD operations for drivers, teams, circuits and races, "
        "plus advanced analytics endpoints for performance trends and comparisons."
    )

    # Rate limiting
    RATE_LIMIT_PER_MINUTE: int = 60

    # CORS
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:8000"

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_origins(cls, v: str) -> str:
        # Keep as string; we parse it into a list in the property below
        return v

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        # Accept either sync URLs (sqlite:///..., mysql+pymysql://...) or
        # already-async URLs so Django and FastAPI can share the same env var.
        return to_async_database_url(value)

    @property
    def allowed_origins_list(self) -> List[str]:
        """Parse comma-separated ALLOWED_ORIGINS into a Python list."""
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",")]

    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT == "development"

    @property
    def is_sqlite(self) -> bool:
        return "sqlite" in self.DATABASE_URL

# Single global instance - imported everywhere in the app
settings = Settings()
