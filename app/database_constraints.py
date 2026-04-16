"""
Database-level integrity constraints.

The ORM model definitions cover newly-created databases, but SQLite does not
retrofit new constraints into already-existing tables when `create_all()` runs.
These helpers create missing unique indexes idempotently so the current local
database is protected too.
"""

from sqlalchemy import inspect, text

from app.database import Base


UNIQUE_INDEXES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("ix_users_username", "users", ("username",)),
    ("ix_users_email", "users", ("email",)),
    ("ix_drivers_driver_ref", "drivers", ("driver_ref",)),
    ("ix_teams_constructor_ref", "teams", ("constructor_ref",)),
    ("ix_circuits_circuit_ref", "circuits", ("circuit_ref",)),
    ("uq_races_year_round", "races", ("year", "round")),
)


def _quote_identifier(identifier: str) -> str:
    """Safely quote static SQL identifiers used in DDL statements."""
    return '"' + identifier.replace('"', '""') + '"'


def _table_exists(sync_conn, table_name: str) -> bool:
    inspector = inspect(sync_conn)
    return table_name in inspector.get_table_names()


def _has_unique_index(sync_conn, table_name: str, index_name: str, columns: tuple[str, ...]) -> bool:
    """Return True if a matching unique index/constraint already exists."""
    inspector = inspect(sync_conn)
    column_set = set(columns)

    for index in inspector.get_indexes(table_name):
        if index.get("name") == index_name:
            return bool(index.get("unique"))
        if index.get("unique") and set(index.get("column_names") or []) == column_set:
            return True

    for constraint in inspector.get_unique_constraints(table_name):
        if constraint.get("name") == index_name:
            return True
        if set(constraint.get("column_names") or []) == column_set:
            return True

    return False


def _find_duplicate_key(sync_conn, table_name: str, columns: tuple[str, ...]):
    """Return one duplicate key tuple if the table already violates the constraint."""
    quoted_table = _quote_identifier(table_name)
    quoted_columns = ", ".join(_quote_identifier(column) for column in columns)
    sql = text(
        f"""
        SELECT {quoted_columns}
        FROM {quoted_table}
        GROUP BY {quoted_columns}
        HAVING COUNT(*) > 1
        LIMIT 1
        """
    )
    row = sync_conn.execute(sql).first()
    if row is None:
        return None
    return tuple(row)


def ensure_unique_indexes(sync_conn) -> None:
    """
    Create any missing unique indexes required by the application contract.

    This function is intentionally synchronous because SQLAlchemy's
    `AsyncConnection.run_sync()` calls it with a sync connection.
    """
    for index_name, table_name, columns in UNIQUE_INDEXES:
        if not _table_exists(sync_conn, table_name):
            continue
        if _has_unique_index(sync_conn, table_name, index_name, columns):
            continue
        duplicate_key = _find_duplicate_key(sync_conn, table_name, columns)
        if duplicate_key is not None:
            columns_csv = ", ".join(columns)
            raise RuntimeError(
                f"Cannot create unique index {index_name} on {table_name}({columns_csv}) "
                f"because duplicate values already exist: {duplicate_key}"
            )

        quoted_index = _quote_identifier(index_name)
        quoted_table = _quote_identifier(table_name)
        quoted_columns = ", ".join(_quote_identifier(column) for column in columns)
        sync_conn.execute(
            text(f"CREATE UNIQUE INDEX {quoted_index} ON {quoted_table} ({quoted_columns})")
        )


async def create_schema_with_constraints(conn) -> None:
    """Create tables and ensure critical unique indexes exist."""
    await conn.run_sync(Base.metadata.create_all)
    await conn.run_sync(ensure_unique_indexes)
