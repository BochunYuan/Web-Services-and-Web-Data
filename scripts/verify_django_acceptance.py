#!/usr/bin/env python3
"""
Run a Django acceptance verification suite against a temporary database copy.

This keeps the user's main local database untouched while checking the key
behaviours we care about after the Django adapter refactor:

- authentication flow
- CRUD endpoints
- analytics endpoints
- frontend/static/docs entrypoints
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4


ROOT = Path(__file__).resolve().parent.parent
SOURCE_DB = ROOT / "f1_analytics.db"

sys.path.insert(0, str(ROOT))


def _sqlite_url(path: Path) -> str:
    return f"sqlite:///{path}"


def prepare_environment() -> tuple[Path, object]:
    if not SOURCE_DB.exists():
        raise FileNotFoundError(f"Source database not found: {SOURCE_DB}")

    temp_dir = Path(tempfile.mkdtemp(prefix="django_acceptance_"))
    temp_db = temp_dir / "f1_analytics_acceptance.db"
    shutil.copy2(SOURCE_DB, temp_db)

    os.environ["DATABASE_URL"] = _sqlite_url(temp_db)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "f1_django.settings")

    import django

    django.setup()

    return temp_db, django


def assert_status(response, expected: int, label: str) -> None:
    if response.status_code != expected:
        body = getattr(response, "content", b"")
        snippet = body.decode("utf-8", errors="replace")[:500]
        raise AssertionError(
            f"{label}: expected HTTP {expected}, got {response.status_code}\nResponse snippet:\n{snippet}"
        )


def response_text(response) -> str:
    if hasattr(response, "content"):
        return response.content.decode("utf-8", errors="replace")
    return b"".join(response.streaming_content).decode("utf-8", errors="replace")


def json_request(client, method: str, path: str, payload: dict):
    return getattr(client, method)(
        path,
        data=json.dumps(payload),
        content_type="application/json",
    )


def expect(condition: bool, label: str) -> None:
    if not condition:
        raise AssertionError(label)


def run_suite() -> list[str]:
    temp_db, _django = prepare_environment()

    from django.core.management import call_command
    from django.test import Client

    call_command("migrate", interactive=False, fake_initial=True, verbosity=0)

    client = Client()
    notes: list[str] = [f"Temporary database: {temp_db}"]

    unique = uuid4().hex[:8]
    username = f"acceptance_{unique}"
    email = f"{username}@example.com"
    password = "Pass1234"

    # Frontend and docs
    root_response = client.get("/")
    assert_status(root_response, 200, "GET /")
    root_html = response_text(root_response)
    expect("<!DOCTYPE html>" in root_html, "GET / should return HTML")
    expect("window.__API_BASE_PREFIX__" in root_html, "GET / should inject API prefix for the frontend")
    notes.append("Frontend entrypoint OK")

    static_response = client.get("/static/app.js")
    assert_status(static_response, 200, "GET /static/app.js")
    expect("const API = window.__API_BASE_PREFIX__" in response_text(static_response), "app.js should use injected API prefix")
    notes.append("Static frontend asset OK")

    docs_response = client.get("/docs")
    assert_status(docs_response, 200, "GET /docs")
    redoc_response = client.get("/redoc")
    assert_status(redoc_response, 200, "GET /redoc")
    schema_response = client.get("/openapi.json")
    assert_status(schema_response, 200, "GET /openapi.json")
    health_response = client.get("/health")
    assert_status(health_response, 200, "GET /health")
    notes.append("Docs and health endpoints OK")

    # Authentication
    register_response = json_request(
        client,
        "post",
        "/api/v1/auth/register",
        {"username": username, "email": email, "password": password},
    )
    assert_status(register_response, 201, "POST /api/v1/auth/register")
    register_data = register_response.json()
    expect(register_data["username"] == username, "register should echo normalized username")
    expect(register_data["email"] == email, "register should return email")
    notes.append("Register OK")

    login_form_response = client.post(
        "/api/v1/auth/login",
        {"username": username, "password": password},
        format="multipart",
    )
    assert_status(login_form_response, 200, "POST /api/v1/auth/login")
    login_form_data = login_form_response.json()
    access_token = login_form_data["access_token"]
    refresh_token = login_form_data["refresh_token"]
    expect(login_form_data["token_type"] == "bearer", "form login should return bearer tokens")
    notes.append("Form login OK")

    login_json_response = json_request(
        client,
        "post",
        "/api/v1/auth/login/json",
        {"username": username, "password": password},
    )
    assert_status(login_json_response, 200, "POST /api/v1/auth/login/json")
    notes.append("JSON login OK")

    refresh_response = json_request(
        client,
        "post",
        "/api/v1/auth/refresh",
        {"refresh_token": refresh_token},
    )
    assert_status(refresh_response, 200, "POST /api/v1/auth/refresh")
    expect("access_token" in refresh_response.json(), "refresh should return a new access token")
    notes.append("Refresh token OK")

    client.defaults["HTTP_AUTHORIZATION"] = f"Bearer {access_token}"
    me_response = client.get("/api/v1/auth/me")
    assert_status(me_response, 200, "GET /api/v1/auth/me")
    me_data = me_response.json()
    expect(me_data["username"] == username, "auth/me should return the logged-in user")
    notes.append("auth/me OK")

    # Drivers CRUD
    driver_ref = f"accept_driver_{unique}"
    create_driver = json_request(
        client,
        "post",
        "/api/v1/drivers",
        {
            "driver_ref": driver_ref,
            "driver_number": 98,
            "code": "ACD",
            "forename": "Accept",
            "surname": "Driver",
            "dob": "1998-01-01",
            "nationality": "British",
            "url": "https://example.com/driver",
        },
    )
    assert_status(create_driver, 201, "POST /api/v1/drivers")
    driver_id = create_driver.json()["id"]

    list_drivers = client.get("/api/v1/drivers", {"search": "Driver", "limit": 5})
    assert_status(list_drivers, 200, "GET /api/v1/drivers")
    expect(any(item["id"] == driver_id for item in list_drivers.json()["items"]), "driver should appear in filtered list")

    get_driver = client.get(f"/api/v1/drivers/{driver_id}")
    assert_status(get_driver, 200, f"GET /api/v1/drivers/{driver_id}")

    update_driver = json_request(
        client,
        "put",
        f"/api/v1/drivers/{driver_id}",
        {"surname": "DriverUpdated", "nationality": "Canadian"},
    )
    assert_status(update_driver, 200, f"PUT /api/v1/drivers/{driver_id}")
    expect(update_driver.json()["surname"] == "DriverUpdated", "driver update should persist")

    delete_driver = client.delete(f"/api/v1/drivers/{driver_id}")
    assert_status(delete_driver, 204, f"DELETE /api/v1/drivers/{driver_id}")
    notes.append("Drivers CRUD OK")

    # Teams CRUD
    team_ref = f"accept_team_{unique}"
    create_team = json_request(
        client,
        "post",
        "/api/v1/teams",
        {
            "constructor_ref": team_ref,
            "name": f"Acceptance Team {unique}",
            "nationality": "British",
            "url": "https://example.com/team",
        },
    )
    assert_status(create_team, 201, "POST /api/v1/teams")
    team_id = create_team.json()["id"]

    get_team = client.get(f"/api/v1/teams/{team_id}")
    assert_status(get_team, 200, f"GET /api/v1/teams/{team_id}")

    update_team = json_request(
        client,
        "put",
        f"/api/v1/teams/{team_id}",
        {"name": f"Acceptance Team Updated {unique}"},
    )
    assert_status(update_team, 200, f"PUT /api/v1/teams/{team_id}")
    expect("Updated" in update_team.json()["name"], "team update should persist")

    delete_team = client.delete(f"/api/v1/teams/{team_id}")
    assert_status(delete_team, 204, f"DELETE /api/v1/teams/{team_id}")
    notes.append("Teams CRUD OK")

    # Circuits CRUD
    circuit_ref = f"accept_circuit_{unique}"
    create_circuit = json_request(
        client,
        "post",
        "/api/v1/circuits",
        {
            "circuit_ref": circuit_ref,
            "name": f"Acceptance Circuit {unique}",
            "location": "Acceptance City",
            "country": "Acceptance Land",
            "lat": 12.34,
            "lng": 56.78,
            "alt": 100.0,
            "url": "https://example.com/circuit",
        },
    )
    assert_status(create_circuit, 201, "POST /api/v1/circuits")
    circuit_id = create_circuit.json()["id"]

    get_circuit = client.get(f"/api/v1/circuits/{circuit_id}")
    assert_status(get_circuit, 200, f"GET /api/v1/circuits/{circuit_id}")

    update_circuit = json_request(
        client,
        "put",
        f"/api/v1/circuits/{circuit_id}",
        {"country": "Updated Land"},
    )
    assert_status(update_circuit, 200, f"PUT /api/v1/circuits/{circuit_id}")
    expect(update_circuit.json()["country"] == "Updated Land", "circuit update should persist")

    # Race CRUD
    create_race = json_request(
        client,
        "post",
        "/api/v1/races",
        {
            "year": 2099,
            "round": 1,
            "circuit_id": circuit_id,
            "name": f"Acceptance Grand Prix {unique}",
            "race_date": "2099-01-01",
            "race_time": "12:30:00",
            "url": "https://example.com/race",
        },
    )
    assert_status(create_race, 201, "POST /api/v1/races")
    race_id = create_race.json()["id"]
    expect(create_race.json()["circuit"]["id"] == circuit_id, "race create should include nested circuit")

    list_races = client.get("/api/v1/races", {"year": 2099, "limit": 5})
    assert_status(list_races, 200, "GET /api/v1/races")
    expect(any(item["id"] == race_id for item in list_races.json()["items"]), "race should appear in year filter list")

    update_race = json_request(
        client,
        "put",
        f"/api/v1/races/{race_id}",
        {"name": f"Acceptance Grand Prix Updated {unique}", "race_time": "13:00:00"},
    )
    assert_status(update_race, 200, f"PUT /api/v1/races/{race_id}")
    expect("Updated" in update_race.json()["name"], "race update should persist")

    delete_race = client.delete(f"/api/v1/races/{race_id}")
    assert_status(delete_race, 204, f"DELETE /api/v1/races/{race_id}")

    delete_circuit = client.delete(f"/api/v1/circuits/{circuit_id}")
    assert_status(delete_circuit, 204, f"DELETE /api/v1/circuits/{circuit_id}")
    notes.append("Circuits and races CRUD OK")

    # Read-only results endpoints
    list_results = client.get("/api/v1/results", {"driver_id": 1, "limit": 5})
    assert_status(list_results, 200, "GET /api/v1/results")
    results_data = list_results.json()
    expect(results_data["items"], "results list should return items for driver_id=1")
    result_id = results_data["items"][0]["id"]

    get_result = client.get(f"/api/v1/results/{result_id}")
    assert_status(get_result, 200, f"GET /api/v1/results/{result_id}")
    notes.append("Results read-only endpoints OK")

    # Analytics endpoints
    performance = client.get("/api/v1/analytics/drivers/1/performance")
    assert_status(performance, 200, "GET /api/v1/analytics/drivers/1/performance")
    expect("career_summary" in performance.json(), "driver performance should include career_summary")

    compare = client.get("/api/v1/analytics/drivers/compare?driver_ids=1&driver_ids=4")
    assert_status(compare, 200, "GET /api/v1/analytics/drivers/compare")
    expect(compare.json()["drivers_compared"] == 2, "compare should count two drivers")

    standings = client.get("/api/v1/analytics/teams/standings/2023")
    assert_status(standings, 200, "GET /api/v1/analytics/teams/standings/2023")
    expect("standings" in standings.json(), "team standings should include standings list")

    highlights = client.get("/api/v1/analytics/seasons/2023/highlights")
    assert_status(highlights, 200, "GET /api/v1/analytics/seasons/2023/highlights")
    expect(highlights.json()["season"] == 2023, "season highlights should echo year")

    circuit_stats = client.get("/api/v1/analytics/circuits/6/stats")
    assert_status(circuit_stats, 200, "GET /api/v1/analytics/circuits/6/stats")
    expect("circuit" in circuit_stats.json(), "circuit stats should include circuit metadata")

    h2h = client.get("/api/v1/analytics/drivers/1/head-to-head/3")
    assert_status(h2h, 200, "GET /api/v1/analytics/drivers/1/head-to-head/3")
    expect("head_to_head" in h2h.json(), "head-to-head should include summary block")
    notes.append("Analytics endpoints OK")

    # Frontend consistency checks after API activity
    expect(response_text(client.get("/")).count("Recent Results") >= 1, "frontend page should still contain the driver tabs")
    notes.append("Frontend page consistency OK")

    return notes


def main() -> None:
    notes = run_suite()
    print("Django acceptance verification passed.")
    for note in notes:
        print(f"- {note}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"Django acceptance verification failed: {exc}", file=sys.stderr)
        raise
