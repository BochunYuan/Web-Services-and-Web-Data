"""
Team CRUD endpoint tests.

Covers: list, get, create, update, delete + pagination + filters.

These tests use the `seed_f1_data` fixture which pre-populates
Mercedes (id=1) and Red Bull (id=2) into the test database.

Tests that write data (POST/PUT/DELETE) use `auth_client` (pre-authenticated).
Tests that only read data use the plain `client` fixture.
"""

from httpx import AsyncClient

TEAMS = "/api/v1/teams"


class TestListTeams:
    """Tests for GET /api/v1/teams"""

    async def test_list_returns_paginated_response(self, client: AsyncClient, seed_f1_data):
        """List endpoint returns pagination metadata alongside items."""
        r = await client.get(TEAMS)
        assert r.status_code == 200
        body = r.json()
        for key in ["items", "total", "page", "limit", "pages", "has_next", "has_prev"]:
            assert key in body, f"Missing pagination field: {key}"

    async def test_list_contains_seeded_teams(self, client: AsyncClient, seed_f1_data):
        """Seeded teams appear in the list response."""
        r = await client.get(TEAMS)
        assert r.status_code == 200
        names = [team["name"] for team in r.json()["items"]]
        assert "Mercedes" in names
        assert "Red Bull" in names

    async def test_filter_by_nationality(self, client: AsyncClient, seed_f1_data):
        """?nationality=German returns Mercedes."""
        r = await client.get(f"{TEAMS}?nationality=German")
        assert r.status_code == 200
        items = r.json()["items"]
        assert len(items) >= 1
        assert all(team["nationality"] == "German" for team in items)

    async def test_search_by_name(self, client: AsyncClient, seed_f1_data):
        """?search=Red finds Red Bull."""
        r = await client.get(f"{TEAMS}?search=Red")
        assert r.status_code == 200
        items = r.json()["items"]
        assert any(team["name"] == "Red Bull" for team in items)

    async def test_pagination_limit_respected(self, client: AsyncClient, seed_f1_data):
        """?limit=1 returns exactly one item."""
        r = await client.get(f"{TEAMS}?limit=1")
        assert r.status_code == 200
        assert len(r.json()["items"]) == 1


class TestGetTeam:
    """Tests for GET /api/v1/teams/{team_id}"""

    async def test_get_existing_team(self, client: AsyncClient, seed_f1_data):
        """Get Mercedes by ID."""
        r = await client.get(f"{TEAMS}/1")
        assert r.status_code == 200
        body = r.json()
        assert body["id"] == 1
        assert body["constructor_ref"] == "mercedes"
        assert body["name"] == "Mercedes"
        assert body["nationality"] == "German"

    async def test_get_nonexistent_team_returns_404(self, client: AsyncClient, seed_f1_data):
        """Non-existent team ID returns 404."""
        r = await client.get(f"{TEAMS}/99999")
        assert r.status_code == 404
        assert "not found" in r.json()["detail"].lower()


class TestCreateTeam:
    """Tests for POST /api/v1/teams"""

    async def test_create_team_authenticated(self, auth_client: AsyncClient, seed_f1_data):
        """Authenticated user can create a new team."""
        r = await auth_client.post(TEAMS, json={
            "constructor_ref": "mclaren_create",
            "name": "McLaren",
            "nationality": "British",
            "url": "https://example.com/mclaren",
        })
        assert r.status_code == 201
        body = r.json()
        assert body["id"] is not None
        assert body["constructor_ref"] == "mclaren_create"
        assert body["name"] == "McLaren"
        assert body["nationality"] == "British"

    async def test_create_team_unauthenticated_returns_401(self, client: AsyncClient, seed_f1_data):
        """Creating a team without a token returns 401."""
        r = await client.post(TEAMS, json={
            "constructor_ref": "noauth_team",
            "name": "No Auth Racing",
        })
        assert r.status_code == 401

    async def test_create_duplicate_constructor_ref_returns_409(self, auth_client: AsyncClient, seed_f1_data):
        """constructor_ref must be unique."""
        r = await auth_client.post(TEAMS, json={
            "constructor_ref": "mercedes",
            "name": "Duplicate Mercedes",
        })
        assert r.status_code == 409


class TestUpdateTeam:
    """Tests for PUT /api/v1/teams/{team_id}"""

    async def test_update_team_authenticated(self, auth_client: AsyncClient, seed_f1_data):
        """Authenticated user can update a newly created team."""
        create = await auth_client.post(TEAMS, json={
            "constructor_ref": "aston_martin_update",
            "name": "Aston Martin",
            "nationality": "British",
        })
        assert create.status_code == 201
        team_id = create.json()["id"]

        r = await auth_client.put(f"{TEAMS}/{team_id}", json={
            "nationality": "Luxembourgish",
            "url": "https://example.com/aston-martin",
        })
        assert r.status_code == 200
        body = r.json()
        assert body["id"] == team_id
        assert body["nationality"] == "Luxembourgish"
        assert body["url"] == "https://example.com/aston-martin"

    async def test_update_nonexistent_team_returns_404(self, auth_client: AsyncClient, seed_f1_data):
        """Updating a non-existent team returns 404."""
        r = await auth_client.put(f"{TEAMS}/99999", json={"nationality": "French"})
        assert r.status_code == 404

    async def test_update_unauthenticated_returns_401(self, client: AsyncClient, seed_f1_data):
        """PUT without token returns 401."""
        r = await client.put(f"{TEAMS}/1", json={"nationality": "Italian"})
        assert r.status_code == 401


class TestDeleteTeam:
    """Tests for DELETE /api/v1/teams/{team_id}"""

    async def test_delete_team_authenticated(self, auth_client: AsyncClient, seed_f1_data):
        """Create then delete a team."""
        create = await auth_client.post(TEAMS, json={
            "constructor_ref": "haas_delete",
            "name": "Haas",
            "nationality": "American",
        })
        assert create.status_code == 201
        team_id = create.json()["id"]

        r = await auth_client.delete(f"{TEAMS}/{team_id}")
        assert r.status_code == 204
        assert r.content == b""

        r = await auth_client.get(f"{TEAMS}/{team_id}")
        assert r.status_code == 404

    async def test_delete_unauthenticated_returns_401(self, client: AsyncClient, seed_f1_data):
        """DELETE without token returns 401."""
        r = await client.delete(f"{TEAMS}/1")
        assert r.status_code == 401
