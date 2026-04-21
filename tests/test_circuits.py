"""
Circuit CRUD endpoint tests.

Covers: list, get, create, update, delete + pagination + filters.

These tests use the `seed_f1_data` fixture which pre-populates
Silverstone Circuit (id=1) into the test database.

Tests that write data (POST/PUT/DELETE) use `auth_client` (pre-authenticated).
Tests that only read data use the plain `client` fixture.
"""

from httpx import AsyncClient

CIRCUITS = "/api/v1/circuits"


class TestListCircuits:
    """Tests for GET /api/v1/circuits"""

    async def test_list_returns_paginated_response(self, client: AsyncClient, seed_f1_data):
        """List endpoint returns pagination metadata alongside items."""
        r = await client.get(CIRCUITS)
        assert r.status_code == 200
        body = r.json()
        for key in ["items", "total", "page", "limit", "pages", "has_next", "has_prev"]:
            assert key in body, f"Missing pagination field: {key}"

    async def test_list_contains_seeded_circuit(self, client: AsyncClient, seed_f1_data):
        """Seeded Silverstone circuit appears in the list."""
        r = await client.get(CIRCUITS)
        assert r.status_code == 200
        names = [circuit["name"] for circuit in r.json()["items"]]
        assert "Silverstone Circuit" in names

    async def test_filter_by_country(self, client: AsyncClient, seed_f1_data):
        """?country=UK returns the seeded circuit."""
        r = await client.get(f"{CIRCUITS}?country=UK")
        assert r.status_code == 200
        items = r.json()["items"]
        assert len(items) >= 1
        assert all(circuit["country"] == "UK" for circuit in items)

    async def test_search_by_name(self, client: AsyncClient, seed_f1_data):
        """?search=Silver finds Silverstone Circuit."""
        r = await client.get(f"{CIRCUITS}?search=Silver")
        assert r.status_code == 200
        items = r.json()["items"]
        assert any(circuit["name"] == "Silverstone Circuit" for circuit in items)

    async def test_pagination_limit_respected(self, client: AsyncClient, seed_f1_data):
        """?limit=1 returns exactly one item."""
        r = await client.get(f"{CIRCUITS}?limit=1")
        assert r.status_code == 200
        assert len(r.json()["items"]) == 1


class TestGetCircuit:
    """Tests for GET /api/v1/circuits/{circuit_id}"""

    async def test_get_existing_circuit(self, client: AsyncClient, seed_f1_data):
        """Get Silverstone by ID."""
        r = await client.get(f"{CIRCUITS}/1")
        assert r.status_code == 200
        body = r.json()
        assert body["id"] == 1
        assert body["circuit_ref"] == "silverstone"
        assert body["name"] == "Silverstone Circuit"
        assert body["country"] == "UK"

    async def test_get_nonexistent_circuit_returns_404(self, client: AsyncClient, seed_f1_data):
        """Non-existent circuit ID returns 404."""
        r = await client.get(f"{CIRCUITS}/99999")
        assert r.status_code == 404
        assert "not found" in r.json()["detail"].lower()


class TestCreateCircuit:
    """Tests for POST /api/v1/circuits"""

    async def test_create_circuit_authenticated(self, auth_client: AsyncClient, seed_f1_data):
        """Authenticated user can create a new circuit."""
        r = await auth_client.post(CIRCUITS, json={
            "circuit_ref": "monza_create",
            "name": "Autodromo Nazionale Monza",
            "location": "Monza",
            "country": "Italy",
            "lat": 45.6156,
            "lng": 9.2811,
        })
        assert r.status_code == 201
        body = r.json()
        assert body["id"] is not None
        assert body["circuit_ref"] == "monza_create"
        assert body["name"] == "Autodromo Nazionale Monza"
        assert body["country"] == "Italy"

    async def test_create_circuit_unauthenticated_returns_401(self, client: AsyncClient, seed_f1_data):
        """Creating a circuit without a token returns 401."""
        r = await client.post(CIRCUITS, json={
            "circuit_ref": "noauth_circuit",
            "name": "No Auth Circuit",
        })
        assert r.status_code == 401

    async def test_create_duplicate_circuit_ref_returns_409(self, auth_client: AsyncClient, seed_f1_data):
        """circuit_ref must be unique."""
        r = await auth_client.post(CIRCUITS, json={
            "circuit_ref": "silverstone",
            "name": "Duplicate Silverstone",
        })
        assert r.status_code == 409


class TestUpdateCircuit:
    """Tests for PUT /api/v1/circuits/{circuit_id}"""

    async def test_update_circuit_authenticated(self, auth_client: AsyncClient, seed_f1_data):
        """Authenticated user can update a newly created circuit."""
        create = await auth_client.post(CIRCUITS, json={
            "circuit_ref": "spa_update",
            "name": "Spa-Francorchamps",
            "location": "Stavelot",
            "country": "Belgium",
            "lat": 50.4372,
            "lng": 5.9714,
        })
        assert create.status_code == 201
        circuit_id = create.json()["id"]

        r = await auth_client.put(f"{CIRCUITS}/{circuit_id}", json={
            "country": "Belgian",
            "alt": 401.0,
        })
        assert r.status_code == 200
        body = r.json()
        assert body["id"] == circuit_id
        assert body["country"] == "Belgian"
        assert body["alt"] == 401.0

    async def test_update_nonexistent_circuit_returns_404(self, auth_client: AsyncClient, seed_f1_data):
        """Updating a non-existent circuit returns 404."""
        r = await auth_client.put(f"{CIRCUITS}/99999", json={"country": "France"})
        assert r.status_code == 404

    async def test_update_unauthenticated_returns_401(self, client: AsyncClient, seed_f1_data):
        """PUT without token returns 401."""
        r = await client.put(f"{CIRCUITS}/1", json={"country": "England"})
        assert r.status_code == 401


class TestDeleteCircuit:
    """Tests for DELETE /api/v1/circuits/{circuit_id}"""

    async def test_delete_circuit_authenticated(self, auth_client: AsyncClient, seed_f1_data):
        """Create then delete a circuit."""
        create = await auth_client.post(CIRCUITS, json={
            "circuit_ref": "imola_delete",
            "name": "Autodromo Enzo e Dino Ferrari",
            "location": "Imola",
            "country": "Italy",
        })
        assert create.status_code == 201
        circuit_id = create.json()["id"]

        r = await auth_client.delete(f"{CIRCUITS}/{circuit_id}")
        assert r.status_code == 204
        assert r.content == b""

        r = await auth_client.get(f"{CIRCUITS}/{circuit_id}")
        assert r.status_code == 404

    async def test_delete_unauthenticated_returns_401(self, client: AsyncClient, seed_f1_data):
        """DELETE without token returns 401."""
        r = await client.delete(f"{CIRCUITS}/1")
        assert r.status_code == 401
