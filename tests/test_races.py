"""
Race CRUD endpoint tests.

Covers: list, get, create, update, delete + pagination + filters.

These tests use the `seed_f1_data` fixture which pre-populates:
  - race id=1: 2022 round 1 British Grand Prix
  - race id=2: 2022 round 2 Sprint Race
  - race id=3: 2023 round 1 British Grand Prix 2023
  - race id=4: 2023 round 2 Sprint Race 2023

All seeded races are linked to Silverstone Circuit (id=1).
"""

from httpx import AsyncClient

RACES = "/api/v1/races"


class TestListRaces:
    """Tests for GET /api/v1/races"""

    async def test_list_returns_paginated_response_with_nested_circuit(self, client: AsyncClient, seed_f1_data):
        """List endpoint returns pagination metadata and embedded circuit info."""
        r = await client.get(RACES)
        assert r.status_code == 200
        body = r.json()
        for key in ["items", "total", "page", "limit", "pages", "has_next", "has_prev"]:
            assert key in body, f"Missing pagination field: {key}"
        assert body["total"] == 4
        assert any(item["circuit"]["name"] == "Silverstone Circuit" for item in body["items"])

    async def test_list_contains_seeded_races(self, client: AsyncClient, seed_f1_data):
        """Seeded races appear in the list response."""
        r = await client.get(RACES)
        assert r.status_code == 200
        names = [race["name"] for race in r.json()["items"]]
        assert "British Grand Prix" in names
        assert "Sprint Race 2023" in names

    async def test_filter_by_year(self, client: AsyncClient, seed_f1_data):
        """?year=2022 returns exactly the two seeded 2022 races."""
        r = await client.get(f"{RACES}?year=2022")
        assert r.status_code == 200
        items = r.json()["items"]
        assert len(items) == 2
        assert all(race["year"] == 2022 for race in items)

    async def test_search_by_name(self, client: AsyncClient, seed_f1_data):
        """?search=Sprint finds both sprint races."""
        r = await client.get(f"{RACES}?search=Sprint")
        assert r.status_code == 200
        items = r.json()["items"]
        assert len(items) == 2
        assert all("Sprint" in race["name"] for race in items)

    async def test_pagination_limit_respected(self, client: AsyncClient, seed_f1_data):
        """?limit=1 returns exactly one item."""
        r = await client.get(f"{RACES}?limit=1")
        assert r.status_code == 200
        assert len(r.json()["items"]) == 1


class TestGetRace:
    """Tests for GET /api/v1/races/{race_id}"""

    async def test_get_existing_race_includes_circuit(self, client: AsyncClient, seed_f1_data):
        """Get race id=1 and confirm nested circuit information is included."""
        r = await client.get(f"{RACES}/1")
        assert r.status_code == 200
        body = r.json()
        assert body["id"] == 1
        assert body["year"] == 2022
        assert body["round"] == 1
        assert body["name"] == "British Grand Prix"
        assert body["circuit"]["id"] == 1
        assert body["circuit"]["name"] == "Silverstone Circuit"

    async def test_get_nonexistent_race_returns_404(self, client: AsyncClient, seed_f1_data):
        """Non-existent race ID returns 404."""
        r = await client.get(f"{RACES}/99999")
        assert r.status_code == 404
        assert "not found" in r.json()["detail"].lower()


class TestCreateRace:
    """Tests for POST /api/v1/races"""

    async def test_create_race_authenticated(self, auth_client: AsyncClient, seed_f1_data):
        """Authenticated user can create a new race and get mapped date/time fields back."""
        r = await auth_client.post(RACES, json={
            "year": 2024,
            "round": 1,
            "circuit_id": 1,
            "name": "New Season Opener",
            "race_date": "2024-03-02",
            "race_time": "15:00:00",
            "url": "https://example.com/races/new-season-opener",
        })
        assert r.status_code == 201
        body = r.json()
        assert body["id"] is not None
        assert body["year"] == 2024
        assert body["round"] == 1
        assert body["name"] == "New Season Opener"
        assert body["date"] == "2024-03-02"
        assert body["time"] == "15:00:00"
        assert body["circuit"]["id"] == 1
        assert body["circuit"]["name"] == "Silverstone Circuit"

    async def test_create_race_unauthenticated_returns_401(self, client: AsyncClient, seed_f1_data):
        """Creating a race without a token returns 401."""
        r = await client.post(RACES, json={
            "year": 2024,
            "round": 2,
            "circuit_id": 1,
            "name": "No Auth GP",
        })
        assert r.status_code == 401

    async def test_create_duplicate_year_round_returns_409(self, auth_client: AsyncClient, seed_f1_data):
        """(year, round) pair must be unique."""
        r = await auth_client.post(RACES, json={
            "year": 2022,
            "round": 1,
            "circuit_id": 1,
            "name": "Duplicate British Grand Prix",
        })
        assert r.status_code == 409


class TestUpdateRace:
    """Tests for PUT /api/v1/races/{race_id}"""

    async def test_update_race_authenticated(self, auth_client: AsyncClient, seed_f1_data):
        """Authenticated user can update a newly created race."""
        create = await auth_client.post(RACES, json={
            "year": 2025,
            "round": 1,
            "circuit_id": 1,
            "name": "Prototype Grand Prix",
        })
        assert create.status_code == 201
        race_id = create.json()["id"]

        r = await auth_client.put(f"{RACES}/{race_id}", json={
            "name": "Prototype Grand Prix Revised",
            "race_date": "2025-04-06",
            "race_time": "13:30:00",
            "url": "https://example.com/races/prototype-grand-prix-revised",
        })
        assert r.status_code == 200
        body = r.json()
        assert body["id"] == race_id
        assert body["name"] == "Prototype Grand Prix Revised"
        assert body["date"] == "2025-04-06"
        assert body["time"] == "13:30:00"
        assert body["url"] == "https://example.com/races/prototype-grand-prix-revised"

    async def test_update_nonexistent_race_returns_404(self, auth_client: AsyncClient, seed_f1_data):
        """Updating a non-existent race returns 404."""
        r = await auth_client.put(f"{RACES}/99999", json={"name": "Ghost Race"})
        assert r.status_code == 404

    async def test_update_unauthenticated_returns_401(self, client: AsyncClient, seed_f1_data):
        """PUT without token returns 401."""
        r = await client.put(f"{RACES}/1", json={"name": "Unauthorized Rename"})
        assert r.status_code == 401


class TestDeleteRace:
    """Tests for DELETE /api/v1/races/{race_id}"""

    async def test_delete_race_authenticated(self, auth_client: AsyncClient, seed_f1_data):
        """Create then delete a race."""
        create = await auth_client.post(RACES, json={
            "year": 2026,
            "round": 1,
            "circuit_id": 1,
            "name": "Delete Me Grand Prix",
        })
        assert create.status_code == 201
        race_id = create.json()["id"]

        r = await auth_client.delete(f"{RACES}/{race_id}")
        assert r.status_code == 204
        assert r.content == b""

        r = await auth_client.get(f"{RACES}/{race_id}")
        assert r.status_code == 404

    async def test_delete_unauthenticated_returns_401(self, client: AsyncClient, seed_f1_data):
        """DELETE without token returns 401."""
        r = await client.delete(f"{RACES}/1")
        assert r.status_code == 401
