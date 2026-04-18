"""
Tests for analytics cache invalidation.

These tests cover both the low-level cache invalidation helpers and the
end-to-end behavior where write endpoints should invalidate stale analytics
results after a successful transaction commit.
"""

from types import SimpleNamespace

from httpx import AsyncClient

from app.services import cache_service

ANALYTICS = "/api/v1/analytics"
DRIVERS = "/api/v1/drivers"
TEAMS = "/api/v1/teams"
RACES = "/api/v1/races"


class TestCacheServiceInvalidation:
    """Unit tests for deferred cache invalidation helpers."""

    def setup_method(self):
        cache_service.clear_all()

    def test_run_pending_invalidations_clears_marked_scopes(self):
        session = SimpleNamespace(info={})
        cache_service.set_analytics("analytics:key", {"value": 1})
        cache_service.set_season("season:key", {"value": 2})

        cache_service.mark_domain_data_changed(session)
        cache_service.run_pending_invalidations(session)

        assert cache_service.get_analytics("analytics:key") is None
        assert cache_service.get_season("season:key") is None
        assert session.info == {}

    def test_discard_pending_invalidations_keeps_existing_cache_entries(self):
        session = SimpleNamespace(info={})
        cache_service.set_analytics("analytics:key", {"value": 1})
        cache_service.set_season("season:key", {"value": 2})

        cache_service.mark_domain_data_changed(session)
        cache_service.discard_pending_invalidations(session)

        assert cache_service.get_analytics("analytics:key") == {"value": 1}
        assert cache_service.get_season("season:key") == {"value": 2}
        assert session.info == {}


class TestAnalyticsCacheInvalidation:
    """Integration tests proving stale analytics are invalidated by writes."""

    async def test_driver_write_invalidates_driver_performance_cache(self, auth_client: AsyncClient, seed_f1_data):
        cache_service.clear_all()
        try:
            first = await auth_client.get(f"{ANALYTICS}/drivers/1/performance")
            assert first.status_code == 200
            initial = first.json()
            assert initial["driver"]["nationality"] == "British"

            cache_key = "driver_perf:1:None:None"
            cached = cache_service.get_analytics(cache_key)
            assert cached is not None
            assert cached["driver"]["nationality"] == "British"

            update = await auth_client.put(f"{DRIVERS}/1", json={"nationality": "Martian"})
            assert update.status_code == 200

            assert cache_service.get_analytics(cache_key) is None

            refreshed = await auth_client.get(f"{ANALYTICS}/drivers/1/performance")
            assert refreshed.status_code == 200
            assert refreshed.json()["driver"]["nationality"] == "Martian"
        finally:
            restore = await auth_client.put(f"{DRIVERS}/1", json={"nationality": "British"})
            assert restore.status_code == 200
            cache_service.clear_all()

    async def test_team_write_invalidates_season_highlights_cache(self, auth_client: AsyncClient, seed_f1_data):
        cache_service.clear_all()
        try:
            first = await auth_client.get(f"{ANALYTICS}/seasons/2023/highlights")
            assert first.status_code == 200
            initial = first.json()
            assert initial["champion_constructor"]["name"] == "Red Bull"

            cache_key = "season_highlights:2023"
            cached = cache_service.get_season(cache_key)
            assert cached is not None
            assert cached["champion_constructor"]["name"] == "Red Bull"

            update = await auth_client.put(f"{TEAMS}/2", json={"name": "Oracle Red Bull Racing"})
            assert update.status_code == 200

            assert cache_service.get_season(cache_key) is None

            refreshed = await auth_client.get(f"{ANALYTICS}/seasons/2023/highlights")
            assert refreshed.status_code == 200
            assert refreshed.json()["champion_constructor"]["name"] == "Oracle Red Bull Racing"
        finally:
            restore = await auth_client.put(f"{TEAMS}/2", json={"name": "Red Bull"})
            assert restore.status_code == 200
            cache_service.clear_all()

    async def test_failed_write_does_not_invalidate_existing_cache(self, auth_client: AsyncClient, seed_f1_data):
        cache_service.clear_all()
        first = await auth_client.get(f"{ANALYTICS}/seasons/2022/highlights")
        assert first.status_code == 200

        cache_key = "season_highlights:2022"
        cached = cache_service.get_season(cache_key)
        assert cached is not None

        # Duplicate (year, round) should fail with 409 and keep the old cache entry.
        duplicate = await auth_client.post(
            RACES,
            json={
                "year": 2022,
                "round": 1,
                "circuit_id": 1,
                "name": "Duplicate Race",
            },
        )
        assert duplicate.status_code == 409

        still_cached = cache_service.get_season(cache_key)
        assert still_cached is not None
        assert still_cached["season"] == 2022
