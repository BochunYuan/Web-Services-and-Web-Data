"""
Test configuration and shared fixtures.

conftest.py is a special pytest file — pytest automatically loads it before
any test runs. Fixtures defined here are available to ALL test files without
needing to import them.

Key design decisions:
─────────────────────

1. ISOLATED TEST DATABASE
   Tests use a separate SQLite file (test_f1.db) instead of the real database.
   This means:
   - Tests can freely INSERT/DELETE without corrupting production data
   - Tests always start from a known state (no leftover data from previous runs)
   - Tests can run in parallel without stepping on each other

2. FIXTURE SCOPES
   - scope="session": run ONCE for the entire test session (all test files)
     → Used for: creating the test database, seeding F1 data
   - scope="function": run fresh for EVERY test function
     → Used for: HTTP client (ensures each test starts clean)

3. WHY yield IN FIXTURES?
   yield splits a fixture into setup (before yield) and teardown (after yield).
   The teardown always runs, even if a test fails — like a finally block.
   This guarantees test cleanup never leaks state.
"""

import pytest
import pytest_asyncio
import asyncio
from typing import AsyncGenerator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text

# ── Override settings BEFORE importing the app ───────────────────────────────
# We must patch the database URL before FastAPI creates the engine.
# Using a separate test database file prevents any accidental data corruption.
import os
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_f1.db"
os.environ["SECRET_KEY"] = "test-secret-key-not-for-production-use"
os.environ["ENVIRONMENT"] = "test"   # disables rate limiting during tests

# Now import the app (which reads settings at import time)
from app.main import app
from app.database import Base, get_db
from app.database_migrations import upgrade_database_to_head
from app.models import Driver, Team, Circuit, Race, Result  # ensure models are registered
from app.services import cache_service


# ─────────────────────────────────────────────────────────────────────────────
# Test database engine and session factory
# ─────────────────────────────────────────────────────────────────────────────

TEST_DATABASE_URL = "sqlite+aiosqlite:///./test_f1.db"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False,   # suppress SQL output during tests
)

TestSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


# ─────────────────────────────────────────────────────────────────────────────
# Session-scoped fixtures — run ONCE for all tests
# ─────────────────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def setup_test_db():
    """
    Apply Alembic migrations to the test database.
    Runs once before any test, torn down after all tests complete.

    scope="session" means this fixture is shared across all test files —
    we don't want to re-create tables for every single test.
    """
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)   # clean slate
        await conn.execute(text("DROP TABLE IF EXISTS alembic_version"))

    upgrade_database_to_head(TEST_DATABASE_URL)

    yield  # all tests run here

    # Teardown: drop all tables and delete the test database file
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
    await test_engine.dispose()

    import os
    if os.path.exists("test_f1.db"):
        os.remove("test_f1.db")


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def seed_f1_data(setup_test_db):
    """
    Insert a minimal but realistic F1 dataset for testing.

    Why not use the full 26k-row dataset?
    - Tests should be fast (< 5 seconds total)
    - We only need enough data to exercise each query path
    - Controlled data makes assertions predictable
      (we know exactly what results to expect)

    The seed data is carefully chosen to test real scenarios:
    - 2 drivers (Hamilton, Verstappen) with known career stats
    - 2 teams (Mercedes, Red Bull)
    - 1 circuit (Silverstone)
    - 4 races (2 seasons × 2 rounds)
    - 8 results (each driver in each race)
    """
    async with TestSessionLocal() as db:
        # Teams
        mercedes = Team(id=1, constructor_ref="mercedes", name="Mercedes", nationality="German")
        redbull = Team(id=2, constructor_ref="red_bull", name="Red Bull", nationality="Austrian")
        db.add_all([mercedes, redbull])

        # Drivers
        hamilton = Driver(
            id=1, driver_ref="hamilton", forename="Lewis", surname="Hamilton",
            nationality="British", code="HAM", driver_number=44
        )
        verstappen = Driver(
            id=2, driver_ref="verstappen", forename="Max", surname="Verstappen",
            nationality="Dutch", code="VER", driver_number=33
        )
        db.add_all([hamilton, verstappen])

        # Circuit
        silverstone = Circuit(
            id=1, circuit_ref="silverstone", name="Silverstone Circuit",
            location="Silverstone", country="UK", lat=52.0786, lng=-1.01694
        )
        db.add(silverstone)

        # Races — 2022 season: rounds 1 and 2
        race1 = Race(id=1, year=2022, round=1, circuit_id=1, name="British Grand Prix")
        race2 = Race(id=2, year=2022, round=2, circuit_id=1, name="Sprint Race")
        # 2023 season: round 1
        race3 = Race(id=3, year=2023, round=1, circuit_id=1, name="British Grand Prix 2023")
        race4 = Race(id=4, year=2023, round=2, circuit_id=1, name="Sprint Race 2023")
        db.add_all([race1, race2, race3, race4])

        # Results — Hamilton wins race1 and race3; Verstappen wins race2 and race4
        results = [
            # race1: Hamilton 1st, Verstappen 2nd
            Result(id=1, race_id=1, driver_id=1, constructor_id=1, position=1, position_order=1,
                   position_text="1", points=25.0, laps=52, status="Finished", grid=1),
            Result(id=2, race_id=1, driver_id=2, constructor_id=2, position=2, position_order=2,
                   position_text="2", points=18.0, laps=52, status="Finished", grid=2),
            # race2: Verstappen 1st, Hamilton 2nd
            Result(id=3, race_id=2, driver_id=2, constructor_id=2, position=1, position_order=1,
                   position_text="1", points=25.0, laps=52, status="Finished", grid=1),
            Result(id=4, race_id=2, driver_id=1, constructor_id=1, position=2, position_order=2,
                   position_text="2", points=18.0, laps=52, status="Finished", grid=2),
            # race3: Hamilton wins again
            Result(id=5, race_id=3, driver_id=1, constructor_id=1, position=1, position_order=1,
                   position_text="1", points=25.0, laps=52, status="Finished", grid=2),
            Result(id=6, race_id=3, driver_id=2, constructor_id=2, position=2, position_order=2,
                   position_text="2", points=18.0, laps=52, status="Finished", grid=1),
            # race4: Verstappen wins, Hamilton DNF
            Result(id=7, race_id=4, driver_id=2, constructor_id=2, position=1, position_order=1,
                   position_text="1", points=25.0, laps=52, status="Finished", grid=1),
            Result(id=8, race_id=4, driver_id=1, constructor_id=1, position=None, position_order=20,
                   position_text="R", points=0.0, laps=10, status="Engine", grid=2),
        ]
        db.add_all(results)
        await db.commit()

    yield  # tests run with this data available


# ─────────────────────────────────────────────────────────────────────────────
# Function-scoped fixtures — run fresh for EVERY test
# ─────────────────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def client(setup_test_db) -> AsyncGenerator[AsyncClient, None]:
    """
    HTTP test client for the FastAPI app.

    ASGITransport: makes httpx talk directly to the FastAPI app in-memory,
    without starting a real HTTP server. This is:
    - Faster (no network overhead)
    - More reliable (no port conflicts)
    - Identical behavior to real HTTP (same middleware, same routing)

    The app's get_db dependency is overridden to use the test database
    (see override below), so requests hit test_f1.db, not f1_analytics.db.
    """
    # Override the database dependency for this test
    async def override_get_db():
        async with TestSessionLocal() as session:
            try:
                yield session
                await session.commit()
                cache_service.run_pending_invalidations(session)
            except Exception:
                await session.rollback()
                cache_service.discard_pending_invalidations(session)
                raise

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    # Clean up dependency override after each test
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def db_session(setup_test_db):
    """
    Direct AsyncSession access for tests that need to assert database constraints.
    """
    async with TestSessionLocal() as session:
        try:
            yield session
        finally:
            await session.rollback()


@pytest_asyncio.fixture
async def auth_client(client: AsyncClient, seed_f1_data) -> AsyncClient:
    """
    An HTTP client that is already authenticated.

    Registers a test user, logs in, and attaches the Bearer token to all
    subsequent requests. Tests that need authentication use this fixture
    instead of `client`.

    Usage:
        async def test_create_driver(auth_client):
            r = await auth_client.post("/api/v1/drivers", json={...})
            assert r.status_code == 201
    """
    # Register test user
    await client.post("/api/v1/auth/register", json={
        "username": "testadmin",
        "email": "admin@test.com",
        "password": "AdminPass123",
    })
    # Login
    r = await client.post("/api/v1/auth/login", data={
        "username": "testadmin",
        "password": "AdminPass123",
    })
    token = r.json()["access_token"]

    # Attach token to all future requests from this client
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client


# ─────────────────────────────────────────────────────────────────────────────
# Helper: quickly register+login and return a token
# ─────────────────────────────────────────────────────────────────────────────

async def get_auth_token(client: AsyncClient, username: str = "quickuser") -> str:
    """Utility to register + login and return an access token."""
    await client.post("/api/v1/auth/register", json={
        "username": username,
        "email": f"{username}@test.com",
        "password": "TestPass123",
    })
    r = await client.post("/api/v1/auth/login", data={
        "username": username, "password": "TestPass123"
    })
    return r.json()["access_token"]
