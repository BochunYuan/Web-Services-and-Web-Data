"""
Tests for the Alembic migration workflow.

These checks make sure schema creation is no longer dependent on
Base.metadata.create_all() in application startup paths.
"""

from sqlalchemy import create_engine, inspect, text

from app.database import Base
from app.database_migrations import (
    BASELINE_REVISION,
    stamp_existing_baseline_if_needed,
    to_sync_database_url,
    upgrade_database_to_head,
)
import app.models  # noqa: F401 - populate Base.metadata for legacy baseline test


def has_unique_rule(engine, table_name: str, columns: tuple[str, ...]) -> bool:
    inspector = inspect(engine)
    column_set = set(columns)

    for index in inspector.get_indexes(table_name):
        if index.get("unique") and set(index.get("column_names") or []) == column_set:
            return True

    for constraint in inspector.get_unique_constraints(table_name):
        if set(constraint.get("column_names") or []) == column_set:
            return True

    return False


def test_to_sync_database_url_preserves_passwords_and_converts_async_drivers():
    assert to_sync_database_url("sqlite+aiosqlite:///./app.db") == "sqlite:///./app.db"
    assert (
        to_sync_database_url("mysql+aiomysql://user:secret@example.com/db")
        == "mysql+pymysql://user:secret@example.com/db"
    )


def test_upgrade_database_to_head_creates_versioned_schema(tmp_path):
    db_path = tmp_path / "migrated.db"
    database_url = f"sqlite:///{db_path}"

    upgrade_database_to_head(database_url)

    engine = create_engine(database_url)
    try:
        inspector = inspect(engine)
        assert {
            "alembic_version",
            "users",
            "drivers",
            "teams",
            "circuits",
            "races",
            "results",
        }.issubset(set(inspector.get_table_names()))

        with engine.connect() as conn:
            revision = conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        assert revision == BASELINE_REVISION

        assert has_unique_rule(engine, "users", ("username",))
        assert has_unique_rule(engine, "users", ("email",))
        assert has_unique_rule(engine, "drivers", ("driver_ref",))
        assert has_unique_rule(engine, "teams", ("constructor_ref",))
        assert has_unique_rule(engine, "circuits", ("circuit_ref",))
        assert has_unique_rule(engine, "races", ("year", "round"))
    finally:
        engine.dispose()


def test_stamp_existing_baseline_adopts_legacy_create_all_database(tmp_path):
    db_path = tmp_path / "legacy.db"
    database_url = f"sqlite:///{db_path}"
    engine = create_engine(database_url)
    try:
        Base.metadata.create_all(engine)
    finally:
        engine.dispose()

    assert stamp_existing_baseline_if_needed(database_url) is True
    assert stamp_existing_baseline_if_needed(database_url) is False

    engine = create_engine(database_url)
    try:
        with engine.connect() as conn:
            revision = conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        assert revision == BASELINE_REVISION
    finally:
        engine.dispose()
