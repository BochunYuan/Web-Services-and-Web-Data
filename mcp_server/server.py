"""
F1 Analytics MCP Server
========================
Exposes the F1 Analytics API as a set of AI-callable tools via the
Model Context Protocol (MCP).

What is MCP?
────────────
MCP (Model Context Protocol) is an open standard that lets AI assistants
(like Claude) call external tools and data sources in a structured way.
Instead of asking Claude to "look up Hamilton's stats", you can give Claude
an MCP server and it will call the tool directly, getting structured JSON
back rather than scraping a webpage.

Architecture
────────────
This server is a THIN WRAPPER around our existing API:

  Claude (user asks a question)
       ↓  MCP tool call
  mcp_server/server.py  (this file)
       ↓  async HTTP call to the running FastAPI app
  app/  (our full F1 Analytics API)
       ↓  SQL query
  f1_analytics.db

Why call the API over HTTP rather than importing services directly?
  1. The MCP server is a separate process — it runs alongside the API, not inside it
  2. HTTP calls give us the full API stack (auth, validation, caching) for free
  3. In production, the MCP server calls the deployed PythonAnywhere URL
  4. Easier to demonstrate: you can show Claude calling your live API

Running
────────
Development (with local API):
  # Terminal 1 — start the API
  uvicorn app.main:app --reload

  # Terminal 2 — start the MCP server
  python mcp_server/server.py

Claude Desktop integration (add to claude_desktop_config.json):
  {
    "mcpServers": {
      "f1-analytics": {
        "command": "python",
        "args": ["/path/to/f1-analytics-api/mcp_server/server.py"],
        "env": {
          "F1_API_BASE_URL": "http://127.0.0.1:8000"
        }
      }
    }
  }
"""

import asyncio
import os
import httpx
from fastmcp import FastMCP

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

# F1_API_BASE_URL can be overridden via environment variable.
# Default: local development server.
# Production: set to https://yourusername.pythonanywhere.com
API_BASE = os.environ.get("F1_API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
API_V1 = f"{API_BASE}/api/v1"

# ─────────────────────────────────────────────────────────────────────────────
# MCP Server instance
# ─────────────────────────────────────────────────────────────────────────────

mcp = FastMCP(
    name="F1 Analytics API",
    instructions="""
You have access to a Formula 1 World Championship analytics API covering
race data from 1950 to 2024.

Available tools:
- get_driver_performance: Season-by-season stats for a driver (points, wins, DNFs)
- compare_drivers: Side-by-side career comparison of 2-5 drivers
- get_team_standings: Constructor championship table for a given year
- get_season_highlights: Champion, most wins, and key facts for a season
- get_circuit_stats: Historical win records at a specific circuit
- get_head_to_head: Direct comparison between two drivers in shared races
- search_drivers: Find driver IDs by name (use this first!)
- search_circuits: Find circuit IDs by name

Always use search_drivers or search_circuits first to get the correct IDs,
then call the analytics tools with those IDs.
""",
)

# ─────────────────────────────────────────────────────────────────────────────
# Shared HTTP client factory
# ─────────────────────────────────────────────────────────────────────────────

async def _get(endpoint: str, params: dict = None) -> dict:
    """
    Make a GET request to the F1 API and return the JSON response.

    Using httpx.AsyncClient (not requests) because:
    - MCP tools are async functions
    - httpx has a clean async API identical to requests
    - Supports both sync and async contexts

    timeout=30: analytics queries can take a few seconds on first call
    (before cache warms up), so we give them enough time.
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(f"{API_V1}{endpoint}", params=params)
        r.raise_for_status()
        return r.json()


# ─────────────────────────────────────────────────────────────────────────────
# Helper / discovery tools — used to find IDs before calling analytics
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
async def search_drivers(name: str) -> dict:
    """
    Search for F1 drivers by surname or forename.

    Use this tool FIRST to find a driver's numeric ID before calling
    analytics tools. Returns a list of matching drivers with their IDs.

    Args:
        name: Driver surname or partial name to search for.
              Examples: "hamilton", "verstappen", "schumacher"

    Returns:
        List of matching drivers with id, full name, nationality, and code.

    Example:
        search_drivers("hamilton")
        → [{"id": 1, "name": "Lewis Hamilton", "nationality": "British", "code": "HAM"}]
    """
    data = await _get("/drivers", params={"search": name, "limit": 10})
    return {
        "query": name,
        "results": [
            {
                "id": d["id"],
                "name": f"{d['forename']} {d['surname']}",
                "nationality": d.get("nationality"),
                "code": d.get("code"),
                "number": d.get("driver_number"),
            }
            for d in data["items"]
        ],
        "total_found": data["total"],
    }


@mcp.tool()
async def search_circuits(name: str) -> dict:
    """
    Search for F1 circuits by name or location.

    Use this tool to find a circuit's numeric ID before calling circuit analytics.

    Args:
        name: Circuit name, city, or country to search for.
              Examples: "monaco", "silverstone", "monza", "spa"

    Returns:
        List of matching circuits with id, name, location, and country.
    """
    data = await _get("/circuits", params={"search": name, "limit": 10})
    return {
        "query": name,
        "results": [
            {
                "id": c["id"],
                "name": c["name"],
                "location": c.get("location"),
                "country": c.get("country"),
            }
            for c in data["items"]
        ],
        "total_found": data["total"],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Analytics tools — the 6 core analytical endpoints
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
async def get_driver_performance(
    driver_id: int,
    start_year: int = None,
    end_year: int = None,
) -> dict:
    """
    Get a Formula 1 driver's season-by-season performance statistics.

    Returns points, wins, podiums, races entered, and DNFs for each season
    the driver competed in, plus career totals.

    Args:
        driver_id: Numeric driver ID (use search_drivers to find this).
        start_year: Optional — only return seasons from this year onwards.
        end_year:   Optional — only return seasons up to this year.

    Returns:
        Driver info, list of seasons with stats, and career summary totals.

    Example usage:
        # First find the driver
        search_drivers("hamilton")  → id=1
        # Then get their performance
        get_driver_performance(1, start_year=2014, end_year=2020)
    """
    params = {}
    if start_year:
        params["start_year"] = start_year
    if end_year:
        params["end_year"] = end_year
    return await _get(f"/analytics/drivers/{driver_id}/performance", params=params)


@mcp.tool()
async def compare_drivers(driver_ids: list[int]) -> dict:
    """
    Compare 2–5 Formula 1 drivers side by side across their entire careers.

    Returns total points, wins, podiums, races, win rate, and points-per-race
    for each driver, allowing direct comparison.

    Args:
        driver_ids: List of 2–5 numeric driver IDs to compare.
                    Use search_drivers to find IDs.

    Returns:
        Comparison table with career stats for each driver.

    Example:
        # Compare Hamilton, Vettel, and Alonso
        search_drivers("hamilton")   → id=1
        search_drivers("vettel")     → id=20
        search_drivers("alonso")     → id=4
        compare_drivers([1, 20, 4])
    """
    if len(driver_ids) < 2:
        return {"error": "Provide at least 2 driver IDs"}
    if len(driver_ids) > 5:
        return {"error": "Maximum 5 drivers can be compared"}

    # Build multi-value query string: ?driver_ids=1&driver_ids=20&driver_ids=4
    params = [("driver_ids", did) for did in driver_ids]
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(f"{API_V1}/analytics/drivers/compare", params=params)
        r.raise_for_status()
        return r.json()


@mcp.tool()
async def get_team_standings(year: int) -> dict:
    """
    Get the Formula 1 Constructor Championship standings for a given season.

    Returns all teams ranked by total points, with wins and race entries.
    Matches the official F1 Constructors' Championship table.

    Args:
        year: Championship season year (1950–2024).

    Returns:
        Ranked list of constructors with points, wins, and race entries.

    Example:
        get_team_standings(2023)
        → Red Bull 860pts (21 wins), Mercedes 409pts (1 win), ...
    """
    return await _get(f"/analytics/teams/standings/{year}")


@mcp.tool()
async def get_season_highlights(year: int) -> dict:
    """
    Get a summary of key highlights and champions for a Formula 1 season.

    Returns the Driver Champion, Constructor Champion, driver with most wins,
    number of unique race winners, total races held, and total points scored.

    Args:
        year: Season year (1950–2024).

    Returns:
        Season summary including both champions and key statistics.

    Example:
        get_season_highlights(2021)
        → champion: Max Verstappen (395.5 pts),
          constructor champion: Red Bull,
          most wins: Verstappen (10), unique winners: 3
    """
    return await _get(f"/analytics/seasons/{year}/highlights")


@mcp.tool()
async def get_circuit_stats(circuit_id: int) -> dict:
    """
    Get historical race statistics for a specific Formula 1 circuit.

    Returns total times hosted, year range, top 5 drivers by wins at this
    circuit, and the most successful constructor.

    Args:
        circuit_id: Numeric circuit ID (use search_circuits to find this).

    Returns:
        Circuit details, hosting history, and all-time win records.

    Example:
        # Senna won Monaco 6 times — let's verify
        search_circuits("monaco")  → id=6
        get_circuit_stats(6)
        → top winners: [Ayrton Senna: 6 wins, ...]
    """
    return await _get(f"/analytics/circuits/{circuit_id}/stats")


@mcp.tool()
async def get_head_to_head(driver_id: int, rival_id: int) -> dict:
    """
    Get the head-to-head record between two Formula 1 drivers.

    Compares drivers only in races where BOTH competed. Returns how many
    times each driver finished ahead of the other, win percentages, and
    points scored in their shared races.

    Args:
        driver_id: First driver's numeric ID.
        rival_id:  Second driver's numeric ID.

    Returns:
        Shared race count, head-to-head wins for each driver, win percentages,
        and points scored in shared races.

    Example:
        # Hamilton vs Rosberg — who won the team battle?
        search_drivers("hamilton") → id=1
        search_drivers("rosberg")  → id=3
        get_head_to_head(1, 3)
        → shared_races: 161, hamilton_wins: 97, rosberg_wins: 64, ...
    """
    return await _get(f"/analytics/drivers/{driver_id}/head-to-head/{rival_id}")


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"Starting F1 Analytics MCP Server")
    print(f"Connecting to API at: {API_BASE}")
    print(f"Tools available: {[t for t in dir(mcp) if not t.startswith('_')]}")
    # run() starts the MCP server using stdio transport (default for Claude Desktop)
    mcp.run()
