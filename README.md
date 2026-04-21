# F1 Analytics API

A RESTful API for Formula 1 World Championship data analysis, covering race results from 1950 to 2024. The maintained architecture now uses FastAPI as the single API and business-logic implementation, while Django 5.2 provides a thin WSGI-friendly deployment adapter for PythonAnywhere-style hosting, static asset delivery, docs endpoints, and route-prefix handling without re-implementing the domain logic a second time.

This removes the earlier dual-stack drift risk: `/api/v1/...` behaviour, OpenAPI schema, authentication flow, CRUD resources, and analytics endpoints all come from the same FastAPI core whether requests enter through ASGI directly or via the Django adapter.

> **Dataset:** [Ergast F1 World Championship (Kaggle)](https://www.kaggle.com/datasets/rohanrao/formula-1-world-championship-1950-2020) — 861 drivers, 212 teams, 77 circuits, 1,125 races, 26,759 race results.

---

## Technology Stack

| Layer | Technology | Reason |
|---|---|---|
| API core | **FastAPI 0.115 + Pydantic 2** | Single source of truth for routes, validation, OpenAPI, and response contracts |
| Deployment adapter | **Django 5.2** | WSGI-compatible deployment, mature settings system, simple `manage.py` workflow |
| Docs surface | **FastAPI OpenAPI + Swagger UI + ReDoc** | `/openapi.json`, `/docs`, and `/redoc` stay in sync with the live API implementation |
| Database | **SQLite verified + `DATABASE_URL` portability** | SQLite is the tested coursework database; non-SQLite deployment paths need matching async SQLAlchemy driver validation |
| ORM | **SQLAlchemy 2.0** | Async data access, explicit query control, shared by API runtime and import tooling |
| Migrations | **Alembic + Django `--fake-initial` adoption** | Versioned schema evolution plus Django-side table adoption for WSGI deployment |
| Authentication | **JWT (python-jose) + bcrypt (passlib)** | Industry-standard stateless auth; bcrypt deliberately slow against brute-force |
| Input Validation | **Pydantic schemas** | Typed request/response contracts and consistent validation errors from one implementation |
| Caching | **cachetools TTLCache** | In-memory TTL cache; analytics queries cached 10–30 min |
| Rate Limiting | **FastAPI middleware + Django adapter** | Per-IP request counting is implemented once in the FastAPI core and reached through the Django proxy |
| Testing | **pytest + `manage.py check` + Django acceptance suite** | Verifies docs, auth, CRUD, analytics, static assets, and frontend parity |
| Static assets | **collectstatic + `STATIC_ROOT`** | Production-safe asset collection for PythonAnywhere or reverse-proxy mapping |
| API Documentation | **Swagger UI + ReDoc + static PDF export** | Runtime docs come from the live FastAPI schema; the committed PDF is regenerated from the same source |

---

## Project Structure

```text
f1-analytics-api/
├── app/
│   ├── main.py               # Single FastAPI application and OpenAPI source
│   ├── routers/              # Auth, CRUD, results, analytics endpoints
│   ├── services/             # Auth, analytics, cache orchestration
│   ├── schemas/              # Pydantic request/response models
│   ├── models/               # SQLAlchemy models
│   └── database*.py          # Shared engine, migrations, and URL normalization
├── f1_django/
│   ├── settings.py           # Environment loading, static, DB adoption, API prefix
│   ├── urls.py               # Docs, health, root page, and API proxy mounting
│   ├── wsgi.py               # WSGI entrypoint for deployment
│   └── asgi.py               # ASGI entrypoint for local compatibility
├── django_api/
│   ├── models.py             # Django table declarations for migrations/adoption
│   ├── views.py              # Thin in-process proxy from Django requests to FastAPI
│   └── migrations/           # Django migrations
├── scripts/
│   ├── import_data.py                  # Shared CSV → DB bulk import
│   ├── import_data_django.py           # Compatibility wrapper around shared import
│   ├── django_openapi.py               # Export FastAPI schema in Django deployments
│   ├── verify_django_acceptance.py     # Temporary-DB end-to-end verification
│   ├── generate_api_documentation_pdf.py
│   ├── generate_technical_report_pdf.py
│   ├── generate_presentation_slides_pdf.py
│   └── generate_presentation_slides_pptx.py
├── static/                   # Frontend dashboard assets
├── docs/                     # Generated PDFs and PPTX deliverables
├── mcp_server/               # MCP integration
├── .env.example
├── manage.py
├── requirements.txt
└── f1_analytics.db
```

---

## Quick Start (Django Adapter / Current Runtime)

### 1. Clone and install dependencies

```bash
git clone https://github.com/BochunYuan/Web-Services-and-Web-Data.git
cd f1-analytics-api
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment

The repository includes a preloaded SQLite database (`f1_analytics.db`) so the
site can start immediately after cloning and installing dependencies.

For local coursework demonstration, you can run with the built-in development
defaults and skip creating `.env` entirely. If you want to customise settings
or prepare for deployment, create `.env` from the example file:

```bash
cp .env.example .env
# Edit .env and set a strong SECRET_KEY:
python -c "import secrets; print(secrets.token_hex(32))"
# Paste the output as the value of SECRET_KEY in .env
```

### 3. Start immediately with the bundled database

```bash
python manage.py check
python manage.py migrate --fake-initial
python manage.py runserver 127.0.0.1:8000
```

This path is the fastest way to run the website locally because the repository
already contains a ready-to-use SQLite database with the F1 data loaded.

### 4. Optional: rebuild the database from the raw dataset

Download from [Kaggle — Ergast F1 Dataset](https://www.kaggle.com/datasets/rohanrao/formula-1-world-championship-1950-2020) and place the following CSV files in `data/`:

```
data/drivers.csv
data/constructors.csv
data/circuits.csv
data/races.csv
data/results.csv
```

### 5. Import data into the database

```bash
python scripts/import_data_django.py
# Expected output:
# drivers 861
# teams 212
# circuits 77
# races 1125
# results 26759

# Verify row counts:
python scripts/import_data_django.py --verify
```

The compatibility wrapper delegates to the shared FastAPI/SQLAlchemy importer,
which applies Alembic migrations before loading the CSV data.

If you later want the Django adapter to adopt an existing `f1_analytics.db`,
run this once so Django records the already-existing tables:

```bash
python manage.py migrate --fake-initial
```

### 6. Start the API server

```bash
python manage.py check
python manage.py runserver 127.0.0.1:8000
```

The API is now running at **http://127.0.0.1:8000**

| URL | Description |
|---|---|
| http://127.0.0.1:8000/docs | Swagger UI — interactive API explorer |
| http://127.0.0.1:8000/redoc | ReDoc — alternative documentation view |
| http://127.0.0.1:8000/ | Frontend dashboard |
| http://127.0.0.1:8000/health | Health check |

---

## Deployment Track

The Django adapter is designed for traditional WSGI deployment targets such as
PythonAnywhere. It serves the static frontend, health endpoint, docs routes,
and `/api/v1/...` proxy while forwarding API behaviour to the single FastAPI
implementation in-process.

### Local Django run

```bash
source venv/bin/activate
python manage.py check
python manage.py migrate --fake-initial
python manage.py runserver 127.0.0.1:8001
```

The `--fake-initial` flag is important when you are reusing an existing
`f1_analytics.db`, because the business tables already exist and Django needs
to adopt them instead of recreating them.

### Direct FastAPI run

If you want to run the core API directly during development, you can also
launch the FastAPI app without Django:

```bash
source venv/bin/activate
uvicorn app.main:app --reload
```

The Django adapter and direct FastAPI entrypoint share the same `DATABASE_URL`,
OpenAPI schema, routers, and business logic.

### Django static files

For production, Django should not serve files from `static/` directly. Use the
standard collect step:

```bash
python manage.py collectstatic --noinput
```

Collected files are written to `STATIC_ROOT`, which defaults to:

```text
./staticfiles
```

You can override this with:

```env
DJANGO_STATIC_ROOT=/home/yourusername/f1-analytics-api/staticfiles
```

### PythonAnywhere notes

If you deploy the Django version on PythonAnywhere:

1. Point the WSGI file at `f1_django.wsgi`.
2. Set your environment variables, especially:
   - `SECRET_KEY`
   - `DATABASE_URL`
   - `DJANGO_ALLOWED_HOSTS`
   - `CSRF_TRUSTED_ORIGINS`
   - `API_V1_PREFIX`
   - `DJANGO_STATIC_ROOT`
3. Run:

```bash
python manage.py migrate --fake-initial
python manage.py collectstatic --noinput
```

4. In the PythonAnywhere Web tab, add a static mapping:

```text
URL: /static/
Directory: /home/yourusername/f1-analytics-api/staticfiles
```

### Configurable API prefix

The Django version now reads `API_V1_PREFIX` from `.env` and applies it to both:

- the backend route mount point
- the frontend dashboard requests

Example:

```env
API_V1_PREFIX=/service/api
```

With that setting, the frontend will automatically call endpoints like:

```text
/service/api/drivers
/service/api/results
/service/api/analytics/seasons/2023/highlights
```

---

## Running Tests

```bash
python manage.py check
python scripts/django_openapi.py --file /tmp/f1_openapi.json
python scripts/verify_django_acceptance.py

# Expected final line:
# Django acceptance verification passed.
```

The acceptance script copies `f1_analytics.db` into a temporary SQLite file,
runs `migrate --fake-initial`, and verifies the frontend, static assets, docs,
registration, login, refresh, authenticated profile, CRUD resources, read-only
results, and all six analytics endpoints without mutating the main database.

---

## API Reference

All endpoints are prefixed with `API_V1_PREFIX`, which defaults to `/api/v1`.
Interactive documentation is available at `/docs`, `/redoc`, and
`/openapi.json`.

### Authentication

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `POST` | `/auth/register` | — | Register new user account |
| `POST` | `/auth/login` | — | Login (form fields), returns JWT pair |
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

Direct comparison in shared races only: wins for each driver, win percentages, and points scored in shared races.

**Example (Hamilton vs Rosberg):**
```json
{
  "driver": { "id": 1, "name": "Lewis Hamilton", "nationality": "British" },
  "rival": { "id": 3, "name": "Nico Rosberg", "nationality": "German" },
  "shared_races": 161,
  "head_to_head": {
    "driver_wins": 97,
    "rival_wins": 64,
    "ties": 0,
    "driver_win_pct": 60.2,
    "rival_win_pct": 39.8
  },
  "points_in_shared_races": {
    "driver_points": 1943.5,
    "rival_points": 1581.0
  }
}
```

---

## Framework Adaptation Status

The Django version has been checked against the behaviours that matter for the
coursework submission:

- registration, form login, JSON login, token refresh, and `auth/me`
- authenticated CRUD for drivers, teams, circuits, and races
- read-only result listing and detail retrieval
- all six analytics endpoints
- `/docs`, `/redoc`, `/openapi.json`, `/health`, `/static/app.js`, and the frontend dashboard
- custom `API_V1_PREFIX` routing and frontend prefix injection
- `collectstatic` dry-run flow for production static files

---

## Security Implementation

| Mechanism | Implementation | Purpose |
|---|---|---|
| Password hashing | bcrypt (cost factor 12) | Slow-by-design: ~100ms per hash, defeating brute-force at the DB level |
| Token authentication | JWT HS256, dual-token (access 30 min + refresh 7 days) | Stateless auth; short access window limits stolen-token damage |
| Input validation | Pydantic request models | Rejects malformed input before it reaches the service layer |
| Rate limiting | Sliding-window, 60 req/min/IP | Prevents brute-force login attempts and scraping |
| CORS | Explicit allow-list (no `*`) | Prevents cross-origin requests from untrusted domains |
| Sensitive config | Django settings + `.env` | Secrets never hardcoded; environment-specific deployment stays configurable |
| Constant-time auth | Dummy hash check on unknown users | Prevents timing attacks that reveal whether a username exists |

---

## Design Decisions and Trade-offs

### Why keep Django after removing the duplicate API implementation?

The coursework API had to remain functionally consistent while fitting a more
traditional deployment target. Django still provides:

- a simple `manage.py` deployment workflow
- WSGI compatibility for PythonAnywhere-style hosts
- straightforward static asset collection via `collectstatic`
- a stable place to mount `/`, `/health`, `/docs`, `/redoc`, and the API prefix

The actual API contracts, validation, and business logic now live only once in
FastAPI, which removes maintenance drift and lowers the amount of framework-
specific code that has to be reasoned about during assessment.

### Why make FastAPI the single implementation?

Keeping two independently maintained API stacks for the same endpoints was not
worth the maintenance cost. By proxying Django requests into `app.main:app`,
the project now has one authoritative implementation for:

- request and response schemas
- authentication and token flows
- CRUD behaviour and conflict handling
- analytics queries and caching
- OpenAPI generation and interactive docs

### Why in-memory caching instead of Redis?

Redis is the production-grade choice for distributed caching. For a single-server deployment on PythonAnywhere, `cachetools.TTLCache` provides identical semantics (TTL expiry, max size, eviction) with zero infrastructure overhead. The cache behaviour is isolated in [app/services/cache_service.py](app/services/cache_service.py) so it can be replaced later without rewriting routers.

### Database schema: Star schema

The `results` table is the central fact table in a star schema: each row records one driver's result in one race, with foreign keys to `drivers`, `teams`, and `races`. This design makes aggregation queries (sum points by season, count wins by circuit) natural SQL GROUP BY operations rather than application-level loops.

### Schema evolution: Alembic baseline + Django `--fake-initial` adoption

Database structure is managed by Alembic in the shared FastAPI/SQLAlchemy
layer. Django does not maintain a second business-schema implementation; when
it needs to align its migration registry with an already-migrated SQLite file,
the adoption flow uses `python manage.py migrate --fake-initial` so Django
records the initial state without recreating the existing tables.

### Static deployment and API prefixing

The adapted stack explicitly supports:

- `collectstatic` for production asset collection
- configurable `STATIC_ROOT`
- configurable `API_V1_PREFIX`
- prefix injection into the frontend dashboard so the browser and backend stay aligned

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

A presentation slide deck covering the architecture diagram, database diagram, demo screenshots, test result, and deployment workflow is available in [docs/presentation_slides.pdf](docs/presentation_slides.pdf).
Regenerate it with `python scripts/generate_presentation_slides_pdf.py`.

## Enter the following terminal command to run：
cd /Users/bochunyuan/Downloads/CWK/Web_service_and_web_data/f1-analytics-api 
python3.11 -m venv venv 
source venv/bin/activate 
pip install -r requirements.txt 
python manage.py migrate --fake-initial 
python manage.py runserver 127.0.0.1:8001 
