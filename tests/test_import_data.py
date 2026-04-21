"""
Tests for scripts/import_data.py.

The import script is mostly data-cleaning and CSV-to-SQL mapping logic, so
these tests use temporary CSV files plus a lightweight fake async connection.
That keeps the coverage fast and deterministic without touching the real
project database.
"""

from pathlib import Path

import pandas as pd
import pytest

from scripts import import_data


class RecordingConnection:
    """Capture execute() calls made by importer functions."""

    def __init__(self):
        self.executions = []

    async def execute(self, statement, params=None):
        self.executions.append({"sql": str(statement), "params": params})


def write_csv(data_dir: Path, filename: str, rows: list[dict]) -> None:
    pd.DataFrame(rows).to_csv(data_dir / filename, index=False)


def inserted_rows(conn: RecordingConnection) -> list[dict]:
    assert len(conn.executions) == 1
    params = conn.executions[0]["params"]
    assert isinstance(params, list)
    return params


class TestSafeValueHelpers:
    """Unit tests for the script's CSV value conversion helpers."""

    @pytest.mark.parametrize("value", [pd.NA, float("nan"), "\\N", "N/A", "NA", "nan", "None", "", "   "])
    def test_nan_to_none_handles_dataset_nulls(self, value):
        assert import_data.nan_to_none(value) is None

    def test_nan_to_none_preserves_non_null_values(self):
        assert import_data.nan_to_none("0") == "0"
        assert import_data.nan_to_none(0) == 0

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("44", 44),
            ("44.0", 44),
            (3.0, 3),
            ("\\N", None),
            ("not-an-int", None),
        ],
    )
    def test_safe_int_converts_numeric_values_or_none(self, value, expected):
        assert import_data.safe_int(value) == expected

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("25.5", 25.5),
            (0, 0.0),
            ("\\N", None),
            ("not-a-float", None),
        ],
    )
    def test_safe_float_converts_numeric_values_or_none(self, value, expected):
        assert import_data.safe_float(value) == expected

    def test_safe_str_trims_truncates_and_handles_nulls(self):
        assert import_data.safe_str("  Hamilton  ") == "Hamilton"
        assert import_data.safe_str("ABCDEFG", max_len=3) == "ABC"
        assert import_data.safe_str("\\N") is None
        assert import_data.safe_str("") is None

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("1985-01-07", "1985-01-07"),
            ("\\N", None),
            ("not-a-date", None),
        ],
    )
    def test_safe_date_returns_iso_date_or_none(self, value, expected):
        assert import_data.safe_date(value) == expected

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("13:30:00", "13:30:00"),
            ("6:00", "06:00:00"),
            ("\\N", None),
            ("not-a-time", None),
        ],
    )
    def test_safe_time_returns_hh_mm_ss_or_none(self, value, expected):
        assert import_data.safe_time(value) == expected


class TestCsvImporters:
    """Tests for importer row mapping and null handling."""

    async def test_missing_csv_returns_zero_and_prints_skip_message(self, tmp_path, capsys):
        conn = RecordingConnection()

        count = await import_data.import_teams(tmp_path, conn)

        assert count == 0
        assert conn.executions == []
        assert "SKIP" in capsys.readouterr().out

    async def test_import_circuits_maps_cleaned_csv_rows(self, tmp_path):
        write_csv(
            tmp_path,
            "circuits.csv",
            [
                {
                    "circuitId": 1,
                    "circuitRef": "silverstone",
                    "name": "Silverstone Circuit",
                    "location": "Silverstone",
                    "country": "UK",
                    "lat": "52.0786",
                    "lng": "-1.01694",
                    "alt": "\\N",
                    "url": "https://example.com/silverstone",
                }
            ],
        )
        conn = RecordingConnection()

        count = await import_data.import_circuits(tmp_path, conn)

        rows = inserted_rows(conn)
        assert count == 1
        assert rows == [
            {
                "id": 1,
                "circuit_ref": "silverstone",
                "name": "Silverstone Circuit",
                "location": "Silverstone",
                "country": "UK",
                "lat": 52.0786,
                "lng": -1.01694,
                "alt": None,
                "url": "https://example.com/silverstone",
            }
        ]

    async def test_import_drivers_maps_defaults_and_truncation(self, tmp_path):
        write_csv(
            tmp_path,
            "drivers.csv",
            [
                {
                    "driverId": 44,
                    "driverRef": "hamilton",
                    "number": "44.0",
                    "code": "HAMX",
                    "forename": "",
                    "surname": "",
                    "dob": "1985-01-07",
                    "nationality": "British",
                    "url": "\\N",
                }
            ],
        )
        conn = RecordingConnection()

        count = await import_data.import_drivers(tmp_path, conn)

        rows = inserted_rows(conn)
        assert count == 1
        assert rows[0] == {
            "id": 44,
            "driver_ref": "hamilton",
            "driver_number": 44,
            "code": "HAM",
            "forename": "Unknown",
            "surname": "Unknown",
            "dob": "1985-01-07",
            "nationality": "British",
            "url": None,
        }

    async def test_import_teams_maps_constructor_csv_rows(self, tmp_path):
        write_csv(
            tmp_path,
            "constructors.csv",
            [
                {
                    "constructorId": 1,
                    "constructorRef": "mercedes",
                    "name": "Mercedes",
                    "nationality": "German",
                    "url": "https://example.com/mercedes",
                }
            ],
        )
        conn = RecordingConnection()

        count = await import_data.import_teams(tmp_path, conn)

        rows = inserted_rows(conn)
        assert count == 1
        assert rows[0] == {
            "id": 1,
            "constructor_ref": "mercedes",
            "name": "Mercedes",
            "nationality": "German",
            "url": "https://example.com/mercedes",
        }

    async def test_import_races_maps_dates_times_and_defaults(self, tmp_path):
        write_csv(
            tmp_path,
            "races.csv",
            [
                {
                    "raceId": 100,
                    "year": 2024,
                    "round": 1,
                    "circuitId": 1,
                    "name": "",
                    "date": "2024-03-02",
                    "time": "6:00",
                    "url": "\\N",
                }
            ],
        )
        conn = RecordingConnection()

        count = await import_data.import_races(tmp_path, conn)

        rows = inserted_rows(conn)
        assert count == 1
        assert rows[0] == {
            "id": 100,
            "year": 2024,
            "round": 1,
            "circuit_id": 1,
            "name": "Unknown Race",
            "date": "2024-03-02",
            "time": "06:00:00",
            "url": None,
        }

    async def test_import_results_maps_chunks_and_result_nulls(self, tmp_path, monkeypatch):
        monkeypatch.setattr(import_data, "tqdm", lambda iterable, **_: iterable)
        write_csv(
            tmp_path,
            "results.csv",
            [
                {
                    "resultId": 1,
                    "raceId": 100,
                    "driverId": 44,
                    "constructorId": 1,
                    "grid": 1,
                    "position": 1,
                    "positionText": "1",
                    "positionOrder": 1,
                    "points": 25,
                    "laps": 57,
                    "time": "1:32:00",
                    "milliseconds": 5520000,
                    "fastestLap": 50,
                    "fastestLapTime": "1:30.000",
                    "fastestLapSpeed": "220.5",
                    "status": "Finished",
                },
                {
                    "resultId": 2,
                    "raceId": 100,
                    "driverId": 1,
                    "constructorId": "\\N",
                    "grid": "\\N",
                    "position": "\\N",
                    "positionText": "R",
                    "positionOrder": 20,
                    "points": "\\N",
                    "laps": 10,
                    "time": "\\N",
                    "milliseconds": "\\N",
                    "fastestLap": "\\N",
                    "fastestLapTime": "\\N",
                    "fastestLapSpeed": "\\N",
                    "status": "Engine",
                },
            ],
        )
        conn = RecordingConnection()

        count = await import_data.import_results(tmp_path, conn)

        rows = inserted_rows(conn)
        assert count == 2
        assert rows[0]["points"] == 25.0
        assert rows[0]["fastest_lap_speed"] == 220.5
        assert rows[1] == {
            "id": 2,
            "race_id": 100,
            "driver_id": 1,
            "constructor_id": None,
            "grid": None,
            "position": None,
            "position_text": "R",
            "position_order": 20,
            "points": 0.0,
            "laps": 10,
            "time_text": None,
            "milliseconds": None,
            "fastest_lap": None,
            "fastest_lap_time": None,
            "fastest_lap_speed": None,
            "status": "Engine",
        }


class TestImportOrchestrator:
    """Tests for main() table selection and reset sequencing."""

    async def test_main_respects_import_order_for_selected_tables(self, monkeypatch):
        calls = []

        class DummyConnection:
            async def run_sync(self, fn):
                calls.append("run_sync")
                fn("sync-connection")

            async def execute(self, statement, params=None):
                calls.append(str(statement).strip())

        class DummyEngine:
            def begin(self):
                return self

            async def __aenter__(self):
                calls.append("engine_begin")
                return DummyConnection()

            async def __aexit__(self, exc_type, exc, tb):
                calls.append("engine_end")
                return False

        def fake_drop_all(sync_conn):
            calls.append(f"drop_all:{sync_conn}")

        def fake_upgrade_database():
            calls.append("upgrade_database")

        def make_importer(name):
            async def fake_importer(data_dir, conn):
                calls.append(f"import:{name}:{data_dir.name}")
                return 1

            return fake_importer

        monkeypatch.setattr(import_data, "engine", DummyEngine())
        monkeypatch.setattr(import_data.Base.metadata, "drop_all", fake_drop_all)
        monkeypatch.setattr(import_data, "upgrade_database_to_head", fake_upgrade_database)
        monkeypatch.setattr(
            import_data,
            "TABLE_IMPORTERS",
            {name: make_importer(name) for name in import_data.IMPORT_ORDER},
        )

        await import_data.main(reset=True, tables=["results", "drivers"])

        assert calls == [
            "engine_begin",
            "run_sync",
            "drop_all:sync-connection",
            "DROP TABLE IF EXISTS alembic_version",
            "engine_end",
            "upgrade_database",
            "engine_begin",
            "import:drivers:data",
            "import:results:data",
            "engine_end",
        ]
