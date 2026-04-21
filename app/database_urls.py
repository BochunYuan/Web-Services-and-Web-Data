from __future__ import annotations

from pathlib import Path

from sqlalchemy.engine import make_url


def to_async_database_url(database_url: str) -> str:
    """Normalize common sync SQLAlchemy URLs into async URLs used by FastAPI."""
    url = make_url(database_url)
    driver_map = {
        "sqlite": "sqlite+aiosqlite",
        "sqlite+pysqlite": "sqlite+aiosqlite",
    }
    return url.set(drivername=driver_map.get(url.drivername, url.drivername)).render_as_string(
        hide_password=False
    )


def sqlite_path_from_url(database_url: str, base_dir: Path) -> str:
    """Resolve sqlite URLs from either the FastAPI or Django URL style."""
    url = make_url(database_url)
    if not url.drivername.startswith("sqlite"):
        return str(base_dir / "f1_analytics.db")

    database = url.database or ""
    if database in {"", ":memory:"}:
        return database or ":memory:"

    path = Path(database)
    return str(path if path.is_absolute() else base_dir / path)
