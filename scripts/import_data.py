"""
F1 Dataset Import Script
========================
Reads Ergast F1 CSV files from the data/ directory and bulk-inserts
them into the SQLite (dev) or MySQL (production) database.

Usage:
    # First time setup — creates tables then imports all data
    python scripts/import_data.py

    # Re-import: drop all data first then re-insert
    python scripts/import_data.py --reset

    # Import only specific tables
    python scripts/import_data.py --tables drivers circuits

Expected CSV files in data/ directory (from Kaggle Ergast dataset):
    drivers.csv, constructors.csv, circuits.csv, races.csv, results.csv

Download from:
    https://www.kaggle.com/datasets/rohanrao/formula-1-world-championship-1950-2020
"""

import sys
import os
import argparse
import asyncio
from pathlib import Path

import pandas as pd
from tqdm import tqdm
from sqlalchemy import text

# Add project root to Python path so we can import `app`
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import engine, Base
from app.database_constraints import create_schema_with_constraints
from app.models import Driver, Team, Circuit, Race, Result  # noqa: F401 — needed for Base.metadata


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

NULL_STRINGS = {"\\N", "N/A", "NA", "nan", "None", ""}


def nan_to_none(value):
    """Convert pandas NaN/NaT or MySQL-style \\N strings to Python None."""
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if str(value).strip() in NULL_STRINGS:
        return None
    return value


def safe_int(value):
    """Convert to int, returning None for NaN/\\N/empty."""
    v = nan_to_none(value)
    if v is None:
        return None
    try:
        return int(float(str(v)))  # handles "3.0" strings too
    except (ValueError, TypeError):
        return None


def safe_float(value):
    """Convert to float, returning None for NaN/\\N/empty."""
    v = nan_to_none(value)
    if v is None:
        return None
    try:
        return float(str(v))
    except (ValueError, TypeError):
        return None


def safe_str(value, max_len=None):
    """Convert to str, returning None for NaN/empty. Truncate if needed."""
    v = nan_to_none(value)
    if v is None:
        return None
    s = str(v).strip()
    if s in ("\\N", "N/A", ""):
        return None
    if max_len:
        s = s[:max_len]
    return s


def safe_date(value):
    """Parse date string, returning ISO format string 'YYYY-MM-DD' or None.
    aiosqlite raw text() SQL does not accept datetime.date objects directly.
    """
    v = nan_to_none(value)
    if v is None:
        return None
    try:
        return pd.to_datetime(v).strftime("%Y-%m-%d")
    except Exception:
        return None


def safe_time(value):
    """Parse time string, returning 'HH:MM:SS' string or None.
    aiosqlite raw text() SQL does not accept datetime.time objects directly.
    """
    v = nan_to_none(value)
    if v is None:
        return None
    try:
        return pd.to_datetime(str(v), format="%H:%M:%S").strftime("%H:%M:%S")
    except Exception:
        try:
            # fallback: some entries are just "6:00" without seconds
            return pd.to_datetime(str(v)).strftime("%H:%M:%S")
        except Exception:
            return None


# ---------------------------------------------------------------------------
# Import functions (one per CSV file)
# ---------------------------------------------------------------------------

async def import_circuits(data_dir: Path, conn) -> int:
    csv_path = data_dir / "circuits.csv"
    if not csv_path.exists():
        print(f"  SKIP: {csv_path} not found")
        return 0

    df = pd.read_csv(csv_path)
    rows = []
    for _, row in df.iterrows():
        rows.append({
            "id": int(row["circuitId"]),
            "circuit_ref": safe_str(row["circuitRef"], 50),
            "name": safe_str(row["name"], 100),
            "location": safe_str(row["location"], 100),
            "country": safe_str(row["country"], 50),
            "lat": safe_float(row["lat"]),
            "lng": safe_float(row["lng"]),
            "alt": safe_float(row.get("alt")),
            "url": safe_str(row.get("url"), 255),
        })

    if rows:
        await conn.execute(
            text("""
                INSERT OR IGNORE INTO circuits
                    (id, circuit_ref, name, location, country, lat, lng, alt, url)
                VALUES
                    (:id, :circuit_ref, :name, :location, :country, :lat, :lng, :alt, :url)
            """),
            rows,
        )
    return len(rows)


async def import_drivers(data_dir: Path, conn) -> int:
    csv_path = data_dir / "drivers.csv"
    if not csv_path.exists():
        print(f"  SKIP: {csv_path} not found")
        return 0

    df = pd.read_csv(csv_path)
    rows = []
    for _, row in df.iterrows():
        rows.append({
            "id": int(row["driverId"]),
            "driver_ref": safe_str(row["driverRef"], 50),
            "driver_number": safe_int(row.get("number")),
            "code": safe_str(row.get("code"), 3),
            "forename": safe_str(row["forename"], 50) or "Unknown",
            "surname": safe_str(row["surname"], 50) or "Unknown",
            "dob": safe_date(row.get("dob")),
            "nationality": safe_str(row.get("nationality"), 50),
            "url": safe_str(row.get("url"), 255),
        })

    if rows:
        await conn.execute(
            text("""
                INSERT OR IGNORE INTO drivers
                    (id, driver_ref, driver_number, code, forename, surname, dob, nationality, url)
                VALUES
                    (:id, :driver_ref, :driver_number, :code, :forename, :surname, :dob, :nationality, :url)
            """),
            rows,
        )
    return len(rows)


async def import_teams(data_dir: Path, conn) -> int:
    csv_path = data_dir / "constructors.csv"
    if not csv_path.exists():
        print(f"  SKIP: {csv_path} not found")
        return 0

    df = pd.read_csv(csv_path)
    rows = []
    for _, row in df.iterrows():
        rows.append({
            "id": int(row["constructorId"]),
            "constructor_ref": safe_str(row["constructorRef"], 50),
            "name": safe_str(row["name"], 100) or "Unknown",
            "nationality": safe_str(row.get("nationality"), 50),
            "url": safe_str(row.get("url"), 255),
        })

    if rows:
        await conn.execute(
            text("""
                INSERT OR IGNORE INTO teams
                    (id, constructor_ref, name, nationality, url)
                VALUES
                    (:id, :constructor_ref, :name, :nationality, :url)
            """),
            rows,
        )
    return len(rows)


async def import_races(data_dir: Path, conn) -> int:
    csv_path = data_dir / "races.csv"
    if not csv_path.exists():
        print(f"  SKIP: {csv_path} not found")
        return 0

    df = pd.read_csv(csv_path)
    rows = []
    for _, row in df.iterrows():
        rows.append({
            "id": int(row["raceId"]),
            "year": int(row["year"]),
            "round": int(row["round"]),
            "circuit_id": safe_int(row["circuitId"]),
            "name": safe_str(row["name"], 100) or "Unknown Race",
            "date": safe_date(row.get("date")),
            "time": safe_time(row.get("time")),
            "url": safe_str(row.get("url"), 255),
        })

    if rows:
        await conn.execute(
            text("""
                INSERT OR IGNORE INTO races
                    (id, year, round, circuit_id, name, date, time, url)
                VALUES
                    (:id, :year, :round, :circuit_id, :name, :date, :time, :url)
            """),
            rows,
        )
    return len(rows)


async def import_results(data_dir: Path, conn) -> int:
    csv_path = data_dir / "results.csv"
    if not csv_path.exists():
        print(f"  SKIP: {csv_path} not found")
        return 0

    df = pd.read_csv(csv_path)
    # Results is the largest file (~25k rows) — process in chunks for progress bar
    chunk_size = 1000
    total = len(df)
    inserted = 0

    for start in tqdm(range(0, total, chunk_size), desc="  results", unit="chunk"):
        chunk = df.iloc[start : start + chunk_size]
        rows = []
        for _, row in chunk.iterrows():
            rows.append({
                "id": int(row["resultId"]),
                "race_id": int(row["raceId"]),
                "driver_id": int(row["driverId"]),
                "constructor_id": safe_int(row.get("constructorId")),
                "grid": safe_int(row.get("grid")),
                "position": safe_int(row.get("position")),
                "position_text": safe_str(row.get("positionText"), 5),
                "position_order": safe_int(row.get("positionOrder")),
                "points": safe_float(row.get("points")) or 0.0,
                "laps": safe_int(row.get("laps")),
                "time_text": safe_str(row.get("time"), 20),
                "milliseconds": safe_int(row.get("milliseconds")),
                "fastest_lap": safe_int(row.get("fastestLap")),
                "fastest_lap_time": safe_str(row.get("fastestLapTime"), 20),
                "fastest_lap_speed": safe_float(row.get("fastestLapSpeed")),
                "status": safe_str(row.get("status"), 50),
            })

        if rows:
            await conn.execute(
                text("""
                    INSERT OR IGNORE INTO results
                        (id, race_id, driver_id, constructor_id, grid, position,
                         position_text, position_order, points, laps, time_text,
                         milliseconds, fastest_lap, fastest_lap_time,
                         fastest_lap_speed, status)
                    VALUES
                        (:id, :race_id, :driver_id, :constructor_id, :grid, :position,
                         :position_text, :position_order, :points, :laps, :time_text,
                         :milliseconds, :fastest_lap, :fastest_lap_time,
                         :fastest_lap_speed, :status)
                """),
                rows,
            )
            inserted += len(rows)

    return inserted


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

TABLE_IMPORTERS = {
    "circuits": import_circuits,
    "drivers": import_drivers,
    "teams": import_teams,
    "races": import_races,
    "results": import_results,
}

# Import order matters due to foreign key constraints:
# circuits must exist before races,
# drivers + teams + races must exist before results
IMPORT_ORDER = ["circuits", "drivers", "teams", "races", "results"]


async def main(reset: bool = False, tables: list[str] = None):
    data_dir = Path(__file__).parent.parent / "data"
    target_tables = tables or IMPORT_ORDER

    print("\n=== F1 Analytics API — Data Import ===\n")

    async with engine.begin() as conn:
        if reset:
            print("⚠  --reset flag detected. Dropping all tables...")
            await conn.run_sync(Base.metadata.drop_all)
            print("   Tables dropped.\n")

        print("Creating tables (if not exist)...")
        await create_schema_with_constraints(conn)
        print("   Tables ready.\n")

        for table_name in IMPORT_ORDER:
            if table_name not in target_tables:
                continue
            importer = TABLE_IMPORTERS[table_name]
            print(f"Importing {table_name}...")
            count = await importer(data_dir, conn)
            print(f"   ✓ {count} rows inserted into {table_name}\n")

    print("=== Import complete! ===\n")
    print("Verify with:")
    print("   python scripts/import_data.py --verify")


async def verify():
    """Print row counts for all tables."""
    from sqlalchemy import select, func
    from app.models import Driver, Team, Circuit, Race, Result

    model_map = {
        "drivers": Driver,
        "teams": Team,
        "circuits": Circuit,
        "races": Race,
        "results": Result,
    }

    print("\n=== Database Row Counts ===")
    async with engine.connect() as conn:
        for name, model in model_map.items():
            result = await conn.execute(select(func.count()).select_from(model))
            count = result.scalar()
            print(f"  {name:<12} {count:>6} rows")
    print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import F1 CSV data into the database")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Drop all tables before importing (full re-import)",
    )
    parser.add_argument(
        "--tables",
        nargs="+",
        choices=list(TABLE_IMPORTERS.keys()),
        help="Import only specific tables (default: all)",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Print row counts and exit",
    )
    args = parser.parse_args()

    if args.verify:
        asyncio.run(verify())
    else:
        asyncio.run(main(reset=args.reset, tables=args.tables))
