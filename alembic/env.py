from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine import make_url

from app.config import settings
from app.database import Base
import app.models  # noqa: F401 - populate Base.metadata for autogenerate


config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


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


def get_database_url() -> str:
    configured_url = config.attributes.get("database_url")
    return to_sync_database_url(configured_url or settings.DATABASE_URL)


def run_migrations_offline() -> None:
    url = get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_database_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
