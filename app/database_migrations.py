"""
Programmatic Alembic integration for application startup, tests, and imports.

The project now uses Alembic as the single source of truth for database schema
evolution. Existing local databases created before Alembic can be adopted only
when they already contain the full expected baseline schema and constraints.
"""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import Connection, make_url

from app.config import settings


PROJECT_ROOT = Path(__file__).resolve().parent.parent
ALEMBIC_INI = PROJECT_ROOT / "alembic.ini"
ALEMBIC_DIR = PROJECT_ROOT / "alembic"
BASELINE_REVISION = "20260420_0001"

BASELINE_TABLES = frozenset(
    {
        "users",
        "drivers",
        "teams",
        "circuits",
        "races",
        "results",
    }
)

BASELINE_UNIQUE_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("users", ("username",)),
    ("users", ("email",)),
    ("drivers", ("driver_ref",)),
    ("teams", ("constructor_ref",)),
    ("circuits", ("circuit_ref",)),
    ("races", ("year", "round")),
)


def to_sync_database_url(database_url: str) -> str:
    """Convert async SQLAlchemy URLs into sync URLs usable by Alembic."""
    url = make_url(database_url)
    driver_map = {
        "sqlite+aiosqlite": "sqlite",
        "postgresql+asyncpg": "postgresql+psycopg",
        "mysql+aiomysql": "mysql+pymysql",
    }
    sync_url = url.set(drivername=driver_map.get(url.drivername, url.drivername))
    return sync_url.render_as_string(hide_password=False)


def make_alembic_config(database_url: str | None = None) -> Config:
    """Build an Alembic Config with absolute paths and an optional DB URL."""
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(ALEMBIC_DIR))
    if database_url:
        config.attributes["database_url"] = database_url
        config.set_main_option("sqlalchemy.url", to_sync_database_url(database_url))
    return config


def _has_unique_rule(connection: Connection, table_name: str, columns: tuple[str, ...]) -> bool:
    inspector = inspect(connection)
    column_set = set(columns)

    for index in inspector.get_indexes(table_name):
        if index.get("unique") and set(index.get("column_names") or []) == column_set:
            return True

    for constraint in inspector.get_unique_constraints(table_name):
        if set(constraint.get("column_names") or []) == column_set:
            return True

    return False


def _assert_existing_schema_can_be_adopted(connection: Connection) -> None:
    inspector = inspect(connection)
    table_names = set(inspector.get_table_names())
    missing_tables = BASELINE_TABLES - table_names
    if missing_tables:
        missing = ", ".join(sorted(missing_tables))
        raise RuntimeError(
            "Cannot adopt existing database into Alembic because required "
            f"baseline tables are missing: {missing}. Run migrations on an "
            "empty database or re-import with `python scripts/import_data.py --reset`."
        )

    missing_unique_rules = [
        f"{table}({', '.join(columns)})"
        for table, columns in BASELINE_UNIQUE_RULES
        if not _has_unique_rule(connection, table, columns)
    ]
    if missing_unique_rules:
        rules = "; ".join(missing_unique_rules)
        raise RuntimeError(
            "Cannot adopt existing database into Alembic because required "
            f"unique constraints/indexes are missing: {rules}. Use a migrated "
            "database or rebuild with `python scripts/import_data.py --reset`."
        )


def stamp_existing_baseline_if_needed(database_url: str | None = None) -> bool:
    """
    Mark a pre-Alembic database as being at the baseline revision.

    Returns True when a stamp was applied. Empty databases are left untouched so
    Alembic can create the schema normally with `upgrade head`.
    """
    resolved_url = database_url or settings.DATABASE_URL
    sync_url = to_sync_database_url(resolved_url)
    engine = create_engine(sync_url)
    try:
        with engine.begin() as connection:
            current_revision = MigrationContext.configure(connection).get_current_revision()
            if current_revision is not None:
                return False

            table_names = set(inspect(connection).get_table_names())
            existing_baseline_tables = table_names & BASELINE_TABLES
            if not existing_baseline_tables:
                return False

            _assert_existing_schema_can_be_adopted(connection)
    finally:
        engine.dispose()

    command.stamp(make_alembic_config(resolved_url), BASELINE_REVISION)
    return True


def upgrade_database_to_head(database_url: str | None = None) -> None:
    """Run Alembic migrations to the latest revision."""
    resolved_url = database_url or settings.DATABASE_URL
    stamp_existing_baseline_if_needed(resolved_url)
    command.upgrade(make_alembic_config(resolved_url), "head")
