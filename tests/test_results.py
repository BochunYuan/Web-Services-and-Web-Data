"""
Results endpoint tests.

Results are read-only (no auth required for reads, no write endpoints).
Tests verify filtering, pagination, and correct data returned.

Seeded data summary:
  race_id=1: results 1 (Hamilton) and 2 (Verstappen)
  race_id=2: results 3 (Verstappen) and 4 (Hamilton)
  race_id=3: results 5 (Hamilton) and 6 (Verstappen)
  race_id=4: results 7 (Verstappen) and 8 (Hamilton, DNF)
  driver_id=1 (Hamilton): result ids 1, 4, 5, 8
  driver_id=2 (Verstappen): result ids 2, 3, 6, 7
"""

import pytest
from httpx import AsyncClient

RESULTS = "/api/v1/results"


class TestListResults:
    """Tests for GET /api/v1/results"""

    async def test_list_results_returns_paginated(self, client: AsyncClient, seed_f1_data):
        """Results list returns pagination envelope."""
        r = await client.get(RESULTS)
        assert r.status_code == 200
        body = r.json()
        assert "items" in body
        assert "total" in body
        assert body["total"] == 8   # 8 seeded results

    async def test_filter_by_race_id(self, client: AsyncClient, seed_f1_data):
        """?race_id=1 returns only results for race 1."""
        r = await client.get(f"{RESULTS}?race_id=1")
        assert r.status_code == 200
        items = r.json()["items"]
        assert len(items) == 2   # Hamilton + Verstappen
        assert all(item["race_id"] == 1 for item in items)

    async def test_filter_by_driver_id(self, client: AsyncClient, seed_f1_data):
        """?driver_id=1 returns only Hamilton's results (4 races)."""
        r = await client.get(f"{RESULTS}?driver_id=1")
        assert r.status_code == 200
        items = r.json()["items"]
        assert len(items) == 4
        assert all(item["driver_id"] == 1 for item in items)

    async def test_filter_by_status_finished(self, client: AsyncClient, seed_f1_data):
        """?status=Finished excludes Hamilton's DNF (Engine)."""
        r = await client.get(f"{RESULTS}?status=Finished")
        assert r.status_code == 200
        items = r.json()["items"]
        assert len(items) == 7   # 8 total - 1 DNF
        assert all(item["status"] == "Finished" for item in items)

    async def test_filter_by_status_engine(self, client: AsyncClient, seed_f1_data):
        """?status=Engine returns only Hamilton's DNF result."""
        r = await client.get(f"{RESULTS}?status=Engine")
        assert r.status_code == 200
        items = r.json()["items"]
        assert len(items) == 1
        assert items[0]["status"] == "Engine"
        assert items[0]["driver_id"] == 1   # Hamilton

    async def test_pagination_limit_enforced(self, client: AsyncClient, seed_f1_data):
        """?limit=200 exceeds max (100) → 422."""
        r = await client.get(f"{RESULTS}?limit=200")
        assert r.status_code == 422

    async def test_pagination_page_2_empty(self, client: AsyncClient, seed_f1_data):
        """Page 2 with limit=8 is empty (only 8 results total)."""
        r = await client.get(f"{RESULTS}?page=2&limit=8")
        assert r.status_code == 200
        assert r.json()["items"] == []


class TestGetResult:
    """Tests for GET /api/v1/results/{id}"""

    async def test_get_result_by_id(self, client: AsyncClient, seed_f1_data):
        """Get result id=1 → Hamilton's win in race 1."""
        r = await client.get(f"{RESULTS}/1")
        assert r.status_code == 200
        body = r.json()
        assert body["id"] == 1
        assert body["driver_id"] == 1        # Hamilton
        assert body["race_id"] == 1
        assert body["position"] == 1         # Won
        assert body["points"] == 25.0

    async def test_get_nonexistent_result_returns_404(self, client: AsyncClient, seed_f1_data):
        """Non-existent result ID returns 404."""
        r = await client.get(f"{RESULTS}/99999")
        assert r.status_code == 404
