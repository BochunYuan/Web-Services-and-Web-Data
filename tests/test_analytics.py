"""
Analytics endpoint tests.

These tests use the seed data from conftest.py:
  Hamilton (id=1):    wins race1, race3 (2 wins)
  Verstappen (id=2):  wins race2, race4 (2 wins)
  Mercedes (id=1):    42+18 = 60 points total (2022 + 2023)
  Red Bull (id=2):    25+25+18+25 = 93 points total

All assertions are based on this controlled dataset, making them
deterministic — the tests don't depend on the full 26k-row F1 dataset.

Why test with controlled data rather than real data?
  Real data: "Hamilton has 103 wins" — but what if the dataset version changes?
  Controlled data: "driver 1 has exactly 2 wins from 4 seeded races" — always true.
"""

import pytest
from httpx import AsyncClient

ANALYTICS = "/api/v1/analytics"


class TestDriverPerformance:
    """Tests for GET /analytics/drivers/{id}/performance"""

    async def test_driver_performance_structure(self, client: AsyncClient, seed_f1_data):
        """Response has the required structure."""
        r = await client.get(f"{ANALYTICS}/drivers/1/performance")
        assert r.status_code == 200
        body = r.json()
        assert "driver" in body
        assert "seasons" in body
        assert "career_summary" in body

    async def test_driver_performance_correct_wins(self, client: AsyncClient, seed_f1_data):
        """Hamilton wins 2 races in the seeded dataset."""
        r = await client.get(f"{ANALYTICS}/drivers/1/performance")
        assert r.status_code == 200
        summary = r.json()["career_summary"]
        assert summary["total_wins"] == 2   # race1 and race3

    async def test_driver_performance_season_fields(self, client: AsyncClient, seed_f1_data):
        """Each season object has all required fields."""
        r = await client.get(f"{ANALYTICS}/drivers/1/performance")
        for season in r.json()["seasons"]:
            for field in ["year", "total_points", "wins", "podiums", "races_entered", "dnfs", "win_rate"]:
                assert field in season, f"Missing field: {field}"

    async def test_driver_performance_year_filter(self, client: AsyncClient, seed_f1_data):
        """start_year/end_year filter restricts seasons returned."""
        r = await client.get(f"{ANALYTICS}/drivers/1/performance?start_year=2023&end_year=2023")
        assert r.status_code == 200
        seasons = r.json()["seasons"]
        assert len(seasons) == 1
        assert seasons[0]["year"] == 2023

    async def test_driver_performance_dnf_counted(self, client: AsyncClient, seed_f1_data):
        """Hamilton's DNF in race4 (Engine) is counted correctly."""
        r = await client.get(f"{ANALYTICS}/drivers/1/performance?start_year=2023&end_year=2023")
        season_2023 = r.json()["seasons"][0]
        assert season_2023["dnfs"] == 1     # race4: status="Engine", position=None

    async def test_driver_performance_404_for_unknown(self, client: AsyncClient, seed_f1_data):
        """Unknown driver_id returns 404."""
        r = await client.get(f"{ANALYTICS}/drivers/99999/performance")
        assert r.status_code == 404


class TestDriverCompare:
    """Tests for GET /analytics/drivers/compare"""

    async def test_compare_two_drivers(self, client: AsyncClient, seed_f1_data):
        """Comparing 2 drivers returns correct structure."""
        r = await client.get(f"{ANALYTICS}/drivers/compare?driver_ids=1&driver_ids=2")
        assert r.status_code == 200
        body = r.json()
        assert body["drivers_compared"] == 2
        assert len(body["comparisons"]) == 2

    async def test_compare_stats_fields(self, client: AsyncClient, seed_f1_data):
        """Each driver entry has all required stats fields."""
        r = await client.get(f"{ANALYTICS}/drivers/compare?driver_ids=1&driver_ids=2")
        for entry in r.json()["comparisons"]:
            stats = entry["stats"]
            for field in ["total_points", "wins", "podiums", "races_entered", "win_rate_pct", "points_per_race"]:
                assert field in stats, f"Missing stats field: {field}"

    async def test_compare_equal_wins(self, client: AsyncClient, seed_f1_data):
        """Hamilton and Verstappen each have 2 wins in seeded data."""
        r = await client.get(f"{ANALYTICS}/drivers/compare?driver_ids=1&driver_ids=2")
        wins = [d["stats"]["wins"] for d in r.json()["comparisons"]]
        assert wins == [2, 2]

    async def test_compare_single_driver_returns_422(self, client: AsyncClient, seed_f1_data):
        """Only 1 driver_id is invalid → 422."""
        r = await client.get(f"{ANALYTICS}/drivers/compare?driver_ids=1")
        assert r.status_code == 422

    async def test_compare_unknown_driver_returns_404(self, client: AsyncClient, seed_f1_data):
        """Unknown driver_id in compare → 404."""
        r = await client.get(f"{ANALYTICS}/drivers/compare?driver_ids=1&driver_ids=99999")
        assert r.status_code == 404


class TestTeamStandings:
    """Tests for GET /analytics/teams/standings/{year}"""

    async def test_standings_structure(self, client: AsyncClient, seed_f1_data):
        """Response has season, standings, total_races fields."""
        r = await client.get(f"{ANALYTICS}/teams/standings/2022")
        assert r.status_code == 200
        body = r.json()
        assert body["season"] == 2022
        assert "standings" in body
        assert "total_races" in body

    async def test_standings_ordered_by_points(self, client: AsyncClient, seed_f1_data):
        """Standings are in descending order by total_points."""
        r = await client.get(f"{ANALYTICS}/teams/standings/2022")
        standings = r.json()["standings"]
        assert len(standings) >= 2
        for i in range(len(standings) - 1):
            assert standings[i]["total_points"] >= standings[i + 1]["total_points"]

    async def test_standings_red_bull_leads_2023(self, client: AsyncClient, seed_f1_data):
        """In seeded 2023 data, Red Bull (Verstappen wins) has more wins."""
        r = await client.get(f"{ANALYTICS}/teams/standings/2023")
        assert r.status_code == 200
        standings = r.json()["standings"]
        # Red Bull (id=2): Verstappen wins race4 (25 pts), Verstappen 2nd race3 (18 pts) = 43 pts
        # Mercedes (id=1): Hamilton wins race3 (25 pts), Hamilton DNF race4 (0 pts) = 25 pts
        # Red Bull leads
        assert standings[0]["team_name"] == "Red Bull"

    async def test_standings_invalid_year_returns_404(self, client: AsyncClient, seed_f1_data):
        """Year with no races returns 404."""
        r = await client.get(f"{ANALYTICS}/teams/standings/1800")
        assert r.status_code == 404


class TestSeasonHighlights:
    """Tests for GET /analytics/seasons/{year}/highlights"""

    async def test_highlights_structure(self, client: AsyncClient, seed_f1_data):
        """Response contains all required fields."""
        r = await client.get(f"{ANALYTICS}/seasons/2022/highlights")
        assert r.status_code == 200
        body = r.json()
        for field in ["season", "total_races", "champion_driver",
                      "champion_constructor", "unique_race_winners"]:
            assert field in body, f"Missing field: {field}"

    async def test_highlights_total_races(self, client: AsyncClient, seed_f1_data):
        """2022 has 2 seeded races → total_races == 2."""
        r = await client.get(f"{ANALYTICS}/seasons/2022/highlights")
        assert r.json()["total_races"] == 2

    async def test_highlights_invalid_season_returns_404(self, client: AsyncClient, seed_f1_data):
        """Season with no data returns 404."""
        r = await client.get(f"{ANALYTICS}/seasons/1800/highlights")
        assert r.status_code == 404


class TestCircuitStats:
    """Tests for GET /analytics/circuits/{id}/stats"""

    async def test_circuit_stats_structure(self, client: AsyncClient, seed_f1_data):
        """Response contains circuit info and race stats."""
        r = await client.get(f"{ANALYTICS}/circuits/1/stats")
        assert r.status_code == 200
        body = r.json()
        assert "circuit" in body
        assert "total_races_hosted" in body
        assert "top_winners" in body

    async def test_circuit_stats_correct_race_count(self, client: AsyncClient, seed_f1_data):
        """Silverstone hosted all 4 seeded races."""
        r = await client.get(f"{ANALYTICS}/circuits/1/stats")
        assert r.json()["total_races_hosted"] == 4

    async def test_circuit_stats_top_winners_list(self, client: AsyncClient, seed_f1_data):
        """top_winners is a non-empty list with driver + wins fields."""
        r = await client.get(f"{ANALYTICS}/circuits/1/stats")
        winners = r.json()["top_winners"]
        assert len(winners) > 0
        assert all("driver" in w and "wins" in w for w in winners)

    async def test_circuit_stats_unknown_circuit_returns_404(self, client: AsyncClient, seed_f1_data):
        """Unknown circuit_id returns 404."""
        r = await client.get(f"{ANALYTICS}/circuits/99999/stats")
        assert r.status_code == 404


class TestHeadToHead:
    """Tests for GET /analytics/drivers/{id}/head-to-head/{rival_id}"""

    async def test_head_to_head_structure(self, client: AsyncClient, seed_f1_data):
        """Response has driver, rival, shared_races, head_to_head fields."""
        r = await client.get(f"{ANALYTICS}/drivers/1/head-to-head/2")
        assert r.status_code == 200
        body = r.json()
        assert "driver" in body
        assert "rival" in body
        assert "shared_races" in body
        assert "head_to_head" in body

    async def test_head_to_head_shared_race_count(self, client: AsyncClient, seed_f1_data):
        """Hamilton and Verstappen share all 4 seeded races."""
        r = await client.get(f"{ANALYTICS}/drivers/1/head-to-head/2")
        assert r.json()["shared_races"] == 4

    async def test_head_to_head_win_counts(self, client: AsyncClient, seed_f1_data):
        """Hamilton wins 2 shared races (race1, race3), Verstappen wins 2 (race2, race4)."""
        r = await client.get(f"{ANALYTICS}/drivers/1/head-to-head/2")
        h2h = r.json()["head_to_head"]
        assert h2h["driver_wins"] == 2   # Hamilton
        assert h2h["rival_wins"] == 2    # Verstappen

    async def test_head_to_head_same_driver_returns_422(self, client: AsyncClient, seed_f1_data):
        """Same driver vs. themselves returns 422."""
        r = await client.get(f"{ANALYTICS}/drivers/1/head-to-head/1")
        assert r.status_code == 422

    async def test_head_to_head_unknown_rival_returns_404(self, client: AsyncClient, seed_f1_data):
        """Unknown rival_id returns 404."""
        r = await client.get(f"{ANALYTICS}/drivers/1/head-to-head/99999")
        assert r.status_code == 404
