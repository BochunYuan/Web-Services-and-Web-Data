"""
MCP server tool tests.

Covers:
  - discovery tools (search_drivers, search_circuits)
  - analytics wrappers that call the shared _get helper
  - compare_drivers validation and multi-value query construction
"""

import httpx

from mcp_server import server


class TestDiscoveryTools:
    """Tests for the MCP search/discovery tools."""

    async def test_search_drivers_formats_results(self, monkeypatch):
        """search_drivers should reshape API items into MCP-friendly summaries."""
        async def fake_get(endpoint: str, params: dict = None):
            assert endpoint == "/drivers"
            assert params == {"search": "hamilton", "limit": 10}
            return {
                "items": [
                    {
                        "id": 1,
                        "forename": "Lewis",
                        "surname": "Hamilton",
                        "nationality": "British",
                        "code": "HAM",
                        "driver_number": 44,
                    }
                ],
                "total": 1,
            }

        monkeypatch.setattr(server, "_get", fake_get)

        result = await server.search_drivers("hamilton")
        assert result == {
            "query": "hamilton",
            "results": [
                {
                    "id": 1,
                    "name": "Lewis Hamilton",
                    "nationality": "British",
                    "code": "HAM",
                    "number": 44,
                }
            ],
            "total_found": 1,
        }

    async def test_search_circuits_formats_results(self, monkeypatch):
        """search_circuits should expose name, location, and country for each hit."""
        async def fake_get(endpoint: str, params: dict = None):
            assert endpoint == "/circuits"
            assert params == {"search": "silverstone", "limit": 10}
            return {
                "items": [
                    {
                        "id": 1,
                        "name": "Silverstone Circuit",
                        "location": "Silverstone",
                        "country": "UK",
                    }
                ],
                "total": 1,
            }

        monkeypatch.setattr(server, "_get", fake_get)

        result = await server.search_circuits("silverstone")
        assert result == {
            "query": "silverstone",
            "results": [
                {
                    "id": 1,
                    "name": "Silverstone Circuit",
                    "location": "Silverstone",
                    "country": "UK",
                }
            ],
            "total_found": 1,
        }


class TestAnalyticsWrappers:
    """Tests for MCP tools that proxy through the shared _get helper."""

    async def test_get_driver_performance_passes_optional_year_filters(self, monkeypatch):
        """Optional start/end year filters should be forwarded only when provided."""
        async def fake_get(endpoint: str, params: dict = None):
            assert endpoint == "/analytics/drivers/1/performance"
            assert params == {"start_year": 2022, "end_year": 2023}
            return {"driver_id": 1, "seasons": []}

        monkeypatch.setattr(server, "_get", fake_get)

        result = await server.get_driver_performance(1, start_year=2022, end_year=2023)
        assert result == {"driver_id": 1, "seasons": []}

    async def test_get_driver_performance_omits_empty_filters(self, monkeypatch):
        """When years are omitted, the helper should receive an empty params dict."""
        async def fake_get(endpoint: str, params: dict = None):
            assert endpoint == "/analytics/drivers/2/performance"
            assert params == {}
            return {"driver_id": 2, "seasons": []}

        monkeypatch.setattr(server, "_get", fake_get)

        result = await server.get_driver_performance(2)
        assert result == {"driver_id": 2, "seasons": []}

    async def test_get_team_standings_uses_expected_endpoint(self, monkeypatch):
        """Team standings should proxy to the constructor standings endpoint."""
        async def fake_get(endpoint: str, params: dict = None):
            assert endpoint == "/analytics/teams/standings/2023"
            assert params is None
            return {"year": 2023, "standings": []}

        monkeypatch.setattr(server, "_get", fake_get)

        result = await server.get_team_standings(2023)
        assert result == {"year": 2023, "standings": []}

    async def test_get_season_highlights_uses_expected_endpoint(self, monkeypatch):
        """Season highlights should proxy to the season summary endpoint."""
        async def fake_get(endpoint: str, params: dict = None):
            assert endpoint == "/analytics/seasons/2022/highlights"
            assert params is None
            return {"year": 2022, "champion": "Max Verstappen"}

        monkeypatch.setattr(server, "_get", fake_get)

        result = await server.get_season_highlights(2022)
        assert result == {"year": 2022, "champion": "Max Verstappen"}

    async def test_get_circuit_stats_uses_expected_endpoint(self, monkeypatch):
        """Circuit stats should target the historical stats route."""
        async def fake_get(endpoint: str, params: dict = None):
            assert endpoint == "/analytics/circuits/6/stats"
            assert params is None
            return {"circuit_id": 6, "race_count": 70}

        monkeypatch.setattr(server, "_get", fake_get)

        result = await server.get_circuit_stats(6)
        assert result == {"circuit_id": 6, "race_count": 70}

    async def test_get_head_to_head_uses_expected_endpoint(self, monkeypatch):
        """Head-to-head should forward both driver IDs into the URL path."""
        async def fake_get(endpoint: str, params: dict = None):
            assert endpoint == "/analytics/drivers/1/head-to-head/2"
            assert params is None
            return {"driver_id": 1, "rival_id": 2, "shared_races": 4}

        monkeypatch.setattr(server, "_get", fake_get)

        result = await server.get_head_to_head(1, 2)
        assert result == {"driver_id": 1, "rival_id": 2, "shared_races": 4}


class TestCompareDrivers:
    """Tests for the special compare_drivers tool."""

    async def test_compare_drivers_requires_at_least_two_ids(self):
        """The MCP helper should reject requests with fewer than two drivers."""
        result = await server.compare_drivers([1])
        assert result == {"error": "Provide at least 2 driver IDs"}

    async def test_compare_drivers_rejects_more_than_five_ids(self):
        """The MCP helper should reject over-large comparison requests."""
        result = await server.compare_drivers([1, 2, 3, 4, 5, 6])
        assert result == {"error": "Maximum 5 drivers can be compared"}

    async def test_compare_drivers_builds_multi_value_query(self, monkeypatch):
        """driver_ids should be sent as repeated query parameters in order."""
        captured = {}

        class DummyResponse:
            def raise_for_status(self):
                return None

            def json(self):
                return {"drivers": [{"id": 1}, {"id": 2}, {"id": 4}]}

        class DummyAsyncClient:
            def __init__(self, *args, **kwargs):
                captured["timeout"] = kwargs.get("timeout")

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def get(self, url, params=None):
                captured["url"] = url
                captured["params"] = params
                return DummyResponse()

        monkeypatch.setattr(server.httpx, "AsyncClient", DummyAsyncClient)

        result = await server.compare_drivers([1, 2, 4])
        assert result == {"drivers": [{"id": 1}, {"id": 2}, {"id": 4}]}
        assert captured["timeout"] == 30.0
        assert captured["url"] == f"{server.API_V1}/analytics/drivers/compare"
        assert captured["params"] == [("driver_ids", 1), ("driver_ids", 2), ("driver_ids", 4)]


class TestSharedGetHelper:
    """Tests for the internal shared HTTP helper used by MCP tools."""

    async def test__get_calls_expected_url_and_returns_json(self, monkeypatch):
        """_get should compose API_V1 + endpoint and return parsed JSON."""
        captured = {}

        class DummyResponse:
            def raise_for_status(self):
                return None

            def json(self):
                return {"ok": True}

        class DummyAsyncClient:
            def __init__(self, *args, **kwargs):
                captured["timeout"] = kwargs.get("timeout")

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def get(self, url, params=None):
                captured["url"] = url
                captured["params"] = params
                return DummyResponse()

        monkeypatch.setattr(server.httpx, "AsyncClient", DummyAsyncClient)

        result = await server._get("/drivers", params={"search": "ham"})
        assert result == {"ok": True}
        assert captured["timeout"] == 30.0
        assert captured["url"] == f"{server.API_V1}/drivers"
        assert captured["params"] == {"search": "ham"}

    async def test__get_propagates_http_errors(self, monkeypatch):
        """HTTP failures from the upstream API should surface to the caller."""
        request = httpx.Request("GET", f"{server.API_V1}/drivers")

        class DummyResponse:
            def raise_for_status(self):
                raise httpx.HTTPStatusError(
                    "boom",
                    request=request,
                    response=httpx.Response(500, request=request),
                )

            def json(self):
                raise AssertionError("json() should not be called after raise_for_status()")

        class DummyAsyncClient:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def get(self, url, params=None):
                return DummyResponse()

        monkeypatch.setattr(server.httpx, "AsyncClient", DummyAsyncClient)

        try:
            await server._get("/drivers")
            raise AssertionError("Expected HTTPStatusError to be raised")
        except httpx.HTTPStatusError as exc:
            assert exc.response.status_code == 500
