from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.config import settings


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------
# create_async_engine creates a connection pool to the database.
#
# connect_args={"check_same_thread": False} is SQLite-specific:
#   SQLite by default only allows the thread that created a connection to use
#   it. FastAPI uses a thread pool, so we disable this restriction.
#   This flag is irrelevant (and harmless to omit) for MySQL.
#
# echo=True prints every SQL statement to stdout during development —
#   very useful for debugging queries. We turn it off in production.

connect_args = {"check_same_thread": False} if settings.is_sqlite else {}

engine = create_async_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=settings.is_development,   # Print SQL in dev, silent in production
)

# ---------------------------------------------------------------------------
# Session factory
# ---------------------------------------------------------------------------
# AsyncSessionLocal is a factory: calling it creates a new database session.
# expire_on_commit=False means ORM objects remain usable after a commit,
# which matters in async code where you might read attributes after committing.

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# ---------------------------------------------------------------------------
# Declarative Base
# ---------------------------------------------------------------------------
# All ORM model classes will inherit from Base.
# SQLAlchemy uses this to track which Python classes map to which DB tables.

class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Dependency function (used by FastAPI's Depends())
# ---------------------------------------------------------------------------
# This is a FastAPI "dependency" — a function FastAPI calls automatically
# to provide a database session to each request handler.
#
# The `async with` / `yield` pattern guarantees:
#   1. A fresh session is created for every request
#   2. The session is always closed when the request finishes,
#      even if an exception is raised (the finally block in __aexit__)
#
# Usage in a router:
#   async def get_drivers(db: AsyncSession = Depends(get_db)):
#       ...

async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
