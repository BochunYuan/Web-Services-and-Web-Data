"""
Database-level uniqueness tests.

These tests intentionally bypass API pre-checks and write directly through the
SQLAlchemy session. If a duplicate insert fails here, the uniqueness rule is
really enforced by the database, not only by router/service code.
"""

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.circuit import Circuit
from app.models.driver import Driver
from app.models.race import Race
from app.models.team import Team
from app.models.user import User


class TestDatabaseUniqueConstraints:
    """Critical uniqueness constraints enforced at the database layer."""

    async def test_user_username_is_unique_in_database(self, db_session):
        """users.username is protected by a DB unique index."""
        db_session.add_all([
            User(username="unique_user", email="one@test.com", hashed_password="hash1"),
            User(username="unique_user", email="two@test.com", hashed_password="hash2"),
        ])

        with pytest.raises(IntegrityError):
            await db_session.commit()

    async def test_user_email_is_unique_in_database(self, db_session):
        """users.email is protected by a DB unique index."""
        db_session.add_all([
            User(username="unique_email_1", email="same@test.com", hashed_password="hash1"),
            User(username="unique_email_2", email="same@test.com", hashed_password="hash2"),
        ])

        with pytest.raises(IntegrityError):
            await db_session.commit()

    async def test_driver_ref_is_unique_in_database(self, db_session, seed_f1_data):
        """drivers.driver_ref is protected by a DB unique index."""
        db_session.add(Driver(
            driver_ref="hamilton",
            forename="Duplicate",
            surname="Hamilton",
        ))

        with pytest.raises(IntegrityError):
            await db_session.commit()

    async def test_constructor_ref_is_unique_in_database(self, db_session, seed_f1_data):
        """teams.constructor_ref is protected by a DB unique index."""
        db_session.add(Team(
            constructor_ref="mercedes",
            name="Duplicate Mercedes",
        ))

        with pytest.raises(IntegrityError):
            await db_session.commit()

    async def test_circuit_ref_is_unique_in_database(self, db_session, seed_f1_data):
        """circuits.circuit_ref is protected by a DB unique index."""
        db_session.add(Circuit(
            circuit_ref="silverstone",
            name="Duplicate Silverstone",
        ))

        with pytest.raises(IntegrityError):
            await db_session.commit()

    async def test_race_year_round_is_unique_in_database(self, db_session, seed_f1_data):
        """races(year, round) is protected by a DB composite unique index."""
        db_session.add(Race(
            year=2022,
            round=1,
            circuit_id=1,
            name="Duplicate British Grand Prix",
        ))

        with pytest.raises(IntegrityError):
            await db_session.commit()
