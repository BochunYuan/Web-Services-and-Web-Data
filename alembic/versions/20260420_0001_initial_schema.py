"""Initial application schema.

Revision ID: 20260420_0001
Revises:
Create Date: 2026-04-20 00:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260420_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "circuits",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("circuit_ref", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("location", sa.String(length=100), nullable=True),
        sa.Column("country", sa.String(length=50), nullable=True),
        sa.Column("lat", sa.Float(), nullable=True),
        sa.Column("lng", sa.Float(), nullable=True),
        sa.Column("alt", sa.Float(), nullable=True),
        sa.Column("url", sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_circuits_circuit_ref", "circuits", ["circuit_ref"], unique=True)
    op.create_index("ix_circuits_country", "circuits", ["country"], unique=False)
    op.create_index("ix_circuits_id", "circuits", ["id"], unique=False)

    op.create_table(
        "drivers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("driver_ref", sa.String(length=50), nullable=False),
        sa.Column("driver_number", sa.Integer(), nullable=True),
        sa.Column("code", sa.String(length=3), nullable=True),
        sa.Column("forename", sa.String(length=50), nullable=False),
        sa.Column("surname", sa.String(length=50), nullable=False),
        sa.Column("dob", sa.Date(), nullable=True),
        sa.Column("nationality", sa.String(length=50), nullable=True),
        sa.Column("url", sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_drivers_driver_ref", "drivers", ["driver_ref"], unique=True)
    op.create_index("ix_drivers_id", "drivers", ["id"], unique=False)
    op.create_index("ix_drivers_nationality", "drivers", ["nationality"], unique=False)
    op.create_index("ix_drivers_surname", "drivers", ["surname"], unique=False)

    op.create_table(
        "teams",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("constructor_ref", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("nationality", sa.String(length=50), nullable=True),
        sa.Column("url", sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_teams_constructor_ref", "teams", ["constructor_ref"], unique=True)
    op.create_index("ix_teams_id", "teams", ["id"], unique=False)
    op.create_index("ix_teams_name", "teams", ["name"], unique=False)

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=50), nullable=False),
        sa.Column("email", sa.String(length=100), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_id", "users", ["id"], unique=False)
    op.create_index("ix_users_username", "users", ["username"], unique=True)

    op.create_table(
        "races",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("round", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("date", sa.Date(), nullable=True),
        sa.Column("time", sa.Time(), nullable=True),
        sa.Column("url", sa.String(length=255), nullable=True),
        sa.Column("circuit_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["circuit_id"], ["circuits.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("year", "round", name="uq_races_year_round"),
    )
    op.create_index("ix_races_circuit_id", "races", ["circuit_id"], unique=False)
    op.create_index("ix_races_id", "races", ["id"], unique=False)
    op.create_index("ix_races_year", "races", ["year"], unique=False)

    op.create_table(
        "results",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("race_id", sa.Integer(), nullable=False),
        sa.Column("driver_id", sa.Integer(), nullable=False),
        sa.Column("constructor_id", sa.Integer(), nullable=True),
        sa.Column("grid", sa.Integer(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=True),
        sa.Column("position_text", sa.String(length=5), nullable=True),
        sa.Column("position_order", sa.Integer(), nullable=True),
        sa.Column("points", sa.Float(), nullable=False),
        sa.Column("laps", sa.Integer(), nullable=True),
        sa.Column("time_text", sa.String(length=20), nullable=True),
        sa.Column("milliseconds", sa.Integer(), nullable=True),
        sa.Column("fastest_lap", sa.Integer(), nullable=True),
        sa.Column("fastest_lap_time", sa.String(length=20), nullable=True),
        sa.Column("fastest_lap_speed", sa.Float(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=True),
        sa.ForeignKeyConstraint(["constructor_id"], ["teams.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["driver_id"], ["drivers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["race_id"], ["races.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_results_constructor_id", "results", ["constructor_id"], unique=False)
    op.create_index("ix_results_driver_id", "results", ["driver_id"], unique=False)
    op.create_index("ix_results_id", "results", ["id"], unique=False)
    op.create_index("ix_results_race_id", "results", ["race_id"], unique=False)
    op.create_index("ix_results_status", "results", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_results_status", table_name="results")
    op.drop_index("ix_results_race_id", table_name="results")
    op.drop_index("ix_results_id", table_name="results")
    op.drop_index("ix_results_driver_id", table_name="results")
    op.drop_index("ix_results_constructor_id", table_name="results")
    op.drop_table("results")

    op.drop_index("ix_races_year", table_name="races")
    op.drop_index("ix_races_id", table_name="races")
    op.drop_index("ix_races_circuit_id", table_name="races")
    op.drop_table("races")

    op.drop_index("ix_users_username", table_name="users")
    op.drop_index("ix_users_id", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")

    op.drop_index("ix_teams_name", table_name="teams")
    op.drop_index("ix_teams_id", table_name="teams")
    op.drop_index("ix_teams_constructor_ref", table_name="teams")
    op.drop_table("teams")

    op.drop_index("ix_drivers_surname", table_name="drivers")
    op.drop_index("ix_drivers_nationality", table_name="drivers")
    op.drop_index("ix_drivers_id", table_name="drivers")
    op.drop_index("ix_drivers_driver_ref", table_name="drivers")
    op.drop_table("drivers")

    op.drop_index("ix_circuits_id", table_name="circuits")
    op.drop_index("ix_circuits_country", table_name="circuits")
    op.drop_index("ix_circuits_circuit_ref", table_name="circuits")
    op.drop_table("circuits")
