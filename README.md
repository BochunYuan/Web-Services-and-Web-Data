# F1 Analytics API

A RESTful API for Formula 1 World Championship data analysis, covering race results from 1950 to 2024. Built with FastAPI, SQLAlchemy, and SQLite/MySQL, it exposes full CRUD operations on F1 entities plus six advanced analytics endpoints — and wraps the entire API as an MCP (Model Context Protocol) server callable by AI assistants.

> **Dataset:** [Ergast F1 World Championship (Kaggle)](https://www.kaggle.com/datasets/rohanrao/formula-1-world-championship-1950-2020) — 861 drivers, 212 teams, 77 circuits, 1,125 races, 26,759 race results.

---

## Technology Stack

| Layer | Technology | Reason |
|---|---|---|
| Framework | **FastAPI 0.115** | Async-native, automatic OpenAPI/Swagger docs, Pydantic v2 validation |
| Database (dev) | **SQLite + aiosqlite** | Zero-config local development; async-compatible |
| Database (prod) | **MySQL (PythonAnywhere)** | Managed, always-on, compatible via SQLAlchemy URL switch |
| ORM | **SQLAlchemy 2.0** | Type-annotated models, async session, DB-agnostic queries |
| Migrations | **Alembic** | Versioned database evolution instead of ad-hoc `create_all()` |
| Authentication | **JWT (python-jose) + bcrypt (passlib)** | Industry-standard stateless auth; bcrypt deliberately slow against brute-force |
| Input Validation | **Pydantic v2** | Strict type coercion, field-level validators, auto 422 on bad input |
| Caching | **cachetools TTLCache** | In-memory sliding-window cache; analytics queries cached 10–30 min |
| Rate Limiting | **Custom sliding-window middleware** | Per-IP request counting; 429 with `Retry-After` header |
| Testing | **pytest + pytest-asyncio + httpx** | Async test client via ASGITransport; isolated test database |
| MCP Server | **FastMCP 2.3** | Exposes analytics tools to AI assistants (Claude Desktop) |
| API Documentation | **Swagger UI + ReDoc** | Auto-generated; zero maintenance; always in sync with code |

---

## Project Structure

```
f1-analytics-api/
├── app/
│   ├── main.py               # FastAPI app, middleware, router registration
│   ├── config.py             # pydantic-settings: typed config from .env
│   ├── database.py           # Async engine, session factory, get_db() dependency
│   ├── database_migrations.py # Alembic startup/test/import integration
│   ├── models/               # SQLAlchemy ORM models (6 tables)
│   │   ├── user.py
│   │   ├── driver.py
│   │   ├── team.py
│   │   ├── circuit.py
│   │   ├── race.py
│   │   └── result.py
│   ├── schemas/              # Pydantic request/response models
│   ├── routers/              # HTTP layer (URL routing, status codes)
│   │   ├── auth.py
│   │   ├── drivers.py
│   │   ├── teams.py
│   │   ├── circuits.py
│   │   ├── races.py
│   │   ├── results.py
│   │   └── analytics.py
│   ├── services/             # Business logic layer (DB-agnostic)
│   │   ├── auth_service.py
│   │   ├── analytics_service.py
│   │   └── cache_service.py
│   └── core/                 # Cross-cutting concerns
│       ├── security.py       # bcrypt hashing + JWT creation/verification
│       ├── dependencies.py   # get_current_user (FastAPI Depends)
│       └── rate_limiter.py   # Sliding-window middleware
├── scripts/
│   └── import_data.py        # CSV → DB bulk import (with --reset, --verify)
├── alembic/
│   ├── env.py                # Alembic environment wired to app metadata
│   └── versions/             # Versioned schema migrations
├── mcp_server/
│   └── server.py             # FastMCP: 8 AI-callable tools
├── tests/
│   ├── conftest.py           # Fixtures: isolated test DB, seed data, auth client
│   ├── test_auth.py          # 11 auth tests
│   ├── test_drivers.py       # 19 CRUD tests
│   ├── test_analytics.py     # 28 analytics tests
│   └── test_results.py       # 9 results tests
├── .env.example
├── requirements.txt
└── pytest.ini
```

---

## Quick Start (Local Development)

### 1. Clone and install dependencies

```bash
git clone <your-repo-url>
cd f1-analytics-api
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env and set a strong SECRET_KEY:
python -c "import secrets; print(secrets.token_hex(32))"
# Paste the output as the value of SECRET_KEY in .env
```

### 3. Download the dataset

Download from [Kaggle — Ergast F1 Dataset](https://www.kaggle.com/datasets/rohanrao/formula-1-world-championship-1950-2020) and place the following CSV files in `data/`:

```
data/drivers.csv
data/constructors.csv
data/circuits.csv
data/races.csv
data/results.csv
```

### 4. Import data into the database

```bash
python scripts/import_data.py
# Expected output:
#   ✓ 77  rows inserted into circuits
#   ✓ 861 rows inserted into drivers
#   ✓ 212 rows inserted into teams
#   ✓ 1125 rows inserted into races
#   ✓ 26759 rows inserted into results

# Verify row counts:
python scripts/import_data.py --verify
```

The import command applies Alembic migrations before loading CSV data. To run
migrations manually, use:

```bash
alembic upgrade head
```

### 5. Start the API server

```bash
uvicorn app.main:app --reload
```

The API is now running at **http://127.0.0.1:8000**

| URL | Description |
|---|---|
| http://127.0.0.1:8000/docs | Swagger UI — interactive API explorer |
| http://127.0.0.1:8000/redoc | ReDoc — alternative documentation view |
| http://127.0.0.1:8000/ | Health check |

---

## Running Tests

```bash
pytest
# 178 tests, ~9 seconds
# Tests use an isolated test_f1.db — production data is never touched
```

---

## API Reference

All endpoints are prefixed with `/api/v1`. Interactive documentation is available at `/docs`.

### Authentication

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `POST` | `/auth/register` | — | Register new user account |
| `POST` | `/auth/login` | — | Login (OAuth2 form), returns JWT pair |
| `POST` | `/auth/login/json` | — | Login (JSON body) |
| `POST` | `/auth/refresh` | — | Exchange refresh token for new access token |
| `GET` | `/auth/me` | Required | Get current user profile |

**Authentication flow:**
```
POST /auth/register  →  { id, username, email, is_active, created_at }
POST /auth/login     →  { access_token, refresh_token, token_type, expires_in }

# Use token on protected endpoints:
Authorization: Bearer <access_token>

# When access token expires (30 min):
POST /auth/refresh  { "refresh_token": "..." }  →  { access_token, ... }
```

---

### Drivers

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/drivers` | — | List drivers (paginated, filterable) |
| `GET` | `/drivers/{id}` | — | Get driver by ID |
| `POST` | `/drivers` | Required | Create new driver |
| `PUT` | `/drivers/{id}` | Required | Update driver (partial update supported) |
| `DELETE` | `/drivers/{id}` | Required | Delete driver |

**Query parameters for `GET /drivers`:**
- `page` (default: 1), `limit` (default: 20, max: 100)
- `nationality` — filter by nationality (e.g. `British`)
- `search` — search by surname (partial, case-insensitive)

**Example:**
```
GET /api/v1/drivers?nationality=British&page=1&limit=5
→ { items: [...], total: 126, page: 1, limit: 5, pages: 26, has_next: true, has_prev: false }
```

---

### Teams (Constructors)

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/teams` | — | List teams (paginated) |
| `GET` | `/teams/{id}` | — | Get team by ID |
| `POST` | `/teams` | Required | Create new team |
| `PUT` | `/teams/{id}` | Required | Update team |
| `DELETE` | `/teams/{id}` | Required | Delete team |

**Query parameters:** `nationality`, `search` (team name), `page`, `limit`

---

### Circuits

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/circuits` | — | List circuits (paginated) |
| `GET` | `/circuits/{id}` | — | Get circuit by ID |
| `POST` | `/circuits` | Required | Create new circuit |
| `PUT` | `/circuits/{id}` | Required | Update circuit |
| `DELETE` | `/circuits/{id}` | Required | Delete circuit |

**Query parameters:** `country`, `search` (circuit name), `page`, `limit`

---

### Races

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/races` | — | List races with nested circuit info (paginated) |
| `GET` | `/races/{id}` | — | Get race by ID |
| `POST` | `/races` | Required | Create new race |
| `PUT` | `/races/{id}` | Required | Update race |
| `DELETE` | `/races/{id}` | Required | Delete race |

**Query parameters:** `year` (e.g. `2023`), `search` (race name), `page`, `limit`

Race responses include nested circuit information:
```json
{
  "id": 1096,
  "year": 2023,
  "round": 1,
  "name": "Bahrain Grand Prix",
  "date": "2023-03-05",
  "circuit": {
    "id": 3,
    "name": "Bahrain International Circuit",
    "country": "Bahrain"
  }
}
```

---

### Results (Read-only)

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/results` | — | List results (paginated, filterable) |
| `GET` | `/results/{id}` | — | Get result by ID |

**Query parameters:** `race_id`, `driver_id`, `status` (e.g. `Finished`, `Engine`), `page`, `limit`

---

### Analytics

All analytics endpoints are **read-only** (no authentication required) and **cached** (repeated calls return instantly after the first request).

#### 1. Driver Season Performance

```
GET /api/v1/analytics/drivers/{driver_id}/performance
    ?start_year=2010&end_year=2023
```

Returns season-by-season breakdown: points, wins, podiums, races entered, DNFs, win rate.

**Example response:**
```json
{
  "driver": { "id": 1, "name": "Lewis Hamilton", "nationality": "British", "code": "HAM" },
  "seasons": [
    { "year": 2014, "total_points": 384.5, "wins": 11, "podiums": 16, "races_entered": 19, "dnfs": 2, "win_rate": 57.9 }
  ],
  "career_summary": { "total_seasons": 17, "total_points": 4639.5, "total_wins": 103, "total_podiums": 197, "total_races": 333 }
}
```

#### 2. Driver Comparison

```
GET /api/v1/analytics/drivers/compare?driver_ids=1&driver_ids=20&driver_ids=4
```

Side-by-side career stats for 2–5 drivers (wins, podiums, points-per-race, win rate %).

#### 3. Team Championship Standings

```
GET /api/v1/analytics/teams/standings/{year}
```

Full constructor championship table for any season, ranked by total points.

**Example (2023):**
```json
{
  "season": 2023,
  "total_races": 22,
  "standings": [
    { "position": 1, "team_name": "Red Bull", "total_points": 860.0, "wins": 21 },
    { "position": 2, "team_name": "Mercedes", "total_points": 409.0, "wins": 1 }
  ]
}
```

#### 4. Season Highlights

```
GET /api/v1/analytics/seasons/{year}/highlights
```

Season summary: driver champion, constructor champion, most wins, unique winners count.

#### 5. Circuit Statistics

```
GET /api/v1/analytics/circuits/{circuit_id}/stats
```

All-time win records at a circuit: top 5 drivers by wins, most successful constructor, hosting history.

#### 6. Head-to-Head

```
GET /api/v1/analytics/drivers/{driver_id}/head-to-head/{rival_id}
```

Direct comparison in shared races only: wins for each driver, win percentages, points scored.

**Example (Hamilton vs Rosberg):**
```json
{
  "shared_races": 161,
  "head_to_head": {
    "driver_wins": 97,
    "rival_wins": 64,
    "driver_win_pct": 60.2,
    "rival_win_pct": 39.8
  }
}
```

---

## MCP Server (AI Tool Integration)

The MCP server wraps the analytics API as tools callable by Claude and other MCP-compatible AI assistants.

### Starting the MCP server

```bash
# Terminal 1 — start the API
uvicorn app.main:app

# Terminal 2 — start the MCP server
python mcp_server/server.py
```

### Claude Desktop integration

Copy the configuration from `mcp_server/claude_desktop_config.json` into your Claude Desktop config file:
- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

Once connected, Claude can answer natural-language F1 questions:
- *"Who won the most races in 2023?"*
- *"Compare Hamilton, Vettel and Alonso's career records"*
- *"What is Hamilton's head-to-head record against Rosberg?"*
- *"Which driver won Monaco the most times?"*

### Available tools

| Tool | Description |
|---|---|
| `search_drivers` | Find driver IDs by name |
| `search_circuits` | Find circuit IDs by name |
| `get_driver_performance` | Season-by-season stats for a driver |
| `compare_drivers` | Side-by-side career comparison |
| `get_team_standings` | Constructor standings for a season |
| `get_season_highlights` | Champion and key stats for a season |
| `get_circuit_stats` | Historical records at a circuit |
| `get_head_to_head` | Direct comparison in shared races |

---

## Security Implementation

| Mechanism | Implementation | Purpose |
|---|---|---|
| Password hashing | bcrypt (cost factor 12) | Slow-by-design: ~100ms per hash, defeating brute-force at the DB level |
| Token authentication | JWT HS256, dual-token (access 30 min + refresh 7 days) | Stateless auth; short access window limits stolen-token damage |
| Input validation | Pydantic v2 strict mode | Rejects malformed input before it reaches the database |
| Rate limiting | Sliding-window, 60 req/min/IP | Prevents brute-force login attempts and scraping |
| CORS | Explicit allow-list (no `*`) | Prevents cross-origin requests from untrusted domains |
| Sensitive config | pydantic-settings + `.env` | Secrets never hardcoded; missing `SECRET_KEY` fails loudly at startup |
| Constant-time auth | Dummy hash check on unknown users | Prevents timing attacks that reveal whether a username exists |

---

## Design Decisions and Trade-offs

### Why FastAPI over Django?

Django is a batteries-included framework suited for traditional server-rendered apps. FastAPI is purpose-built for APIs:
- **Async-native**: every route handler runs asynchronously, supporting high concurrency without threading overhead
- **Auto-documentation**: Swagger UI and ReDoc are generated directly from type annotations — zero maintenance
- **Pydantic integration**: request bodies are validated and serialised automatically; invalid input returns a structured 422 response before any handler code runs

### Why SQLAlchemy 2.0 over a simpler ORM?

SQLAlchemy's async engine with `aiosqlite` (dev) and `pymysql` (production) means the same ORM code runs on both databases with a single URL change. The 2.0 API's `Mapped[T]` annotations also give IDEs full type inference on model attributes, catching errors at development time rather than runtime.

### Why in-memory caching instead of Redis?

Redis is the production-grade choice for distributed caching. For a single-server deployment on PythonAnywhere, `cachetools.TTLCache` provides identical semantics (TTL expiry, max size, eviction) with zero infrastructure overhead. The cache layer is fully abstracted behind `cache_service.py` — switching to Redis requires changing only that file.

### Database schema: Star schema

The `results` table is the central fact table in a star schema: each row records one driver's result in one race, with foreign keys to `drivers`, `teams`, and `races`. This design makes aggregation queries (sum points by season, count wins by circuit) natural SQL GROUP BY operations rather than application-level loops.

### Schema evolution: Alembic migrations

Database structure is managed through Alembic rather than relying on
`Base.metadata.create_all()` at runtime. The initial revision creates the
current six application tables, foreign keys, indexes, and critical uniqueness
rules such as `drivers.driver_ref`, `teams.constructor_ref`, `circuits.circuit_ref`
and `races(year, round)`. Application startup, the CSV import script, and the
test database setup all call the same migration helper, so every environment is
initialised through the same versioned schema path.

### MCP as a novel integration layer

Wrapping a REST API as an MCP server is non-trivial: it requires understanding the tool-call lifecycle, structuring function signatures so an LLM can reason about parameter semantics, and writing `instructions` that guide the model to use discovery tools (`search_drivers`) before analytics tools. The result is an API that is usable not just by HTTP clients but by conversational AI agents — a genuinely novel access pattern for sports analytics data.

---

## API Documentation

Full interactive documentation is auto-generated at runtime:

- **Swagger UI:** `/docs` - try every endpoint directly in the browser, including authenticated ones via the Authorize button
- **ReDoc:** `/redoc` - clean, readable reference documentation
- **OpenAPI JSON:** `/openapi.json` - machine-readable schema for client generation

A static export of the API documentation is available in [docs/api_documentation.pdf](docs/api_documentation.pdf).
Regenerate it with `python scripts/generate_api_documentation_pdf.py`.

## Technical Report

A formal technical report covering stack justification, architecture, challenges, testing, limitations, and the GenAI declaration is available in [docs/technical_report.pdf](docs/technical_report.pdf).
Regenerate it with `python scripts/generate_technical_report_pdf.py`.

## Presentation Slides

A presentation slide deck covering the architecture diagram, database diagram, demo screenshots, test result, and MCP workflow is available in [docs/presentation_slides.pdf](docs/presentation_slides.pdf).
Regenerate it with `python scripts/generate_presentation_slides_pdf.py`.
