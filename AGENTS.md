# GenAI Usage Declaration

**Module:** XJCO3011 Web Services and Web Data
**Project:** F1 Analytics API
**Submission:** Coursework 1

---

## Summary

This project was developed with significant assistance from Claude (Anthropic), used throughout the design, implementation, debugging, and documentation phases. This document declares how GenAI was used, why specific decisions were made, and where the author's own judgment shaped the final result.

---

## How GenAI Was Used

### 1. Architecture Design

Before writing any code, I used Claude to explore architectural options:

- **Q:** *"Should I use FastAPI or Django for a REST API that needs auto-generated documentation?"*
  - Claude explained that FastAPI generates Swagger UI directly from type annotations, eliminating a whole documentation maintenance burden. This informed the framework choice.

- **Q:** *"What is the difference between using SQLAlchemy 2.0 async vs. sync, and which is better for FastAPI?"*
  - Claude explained the event loop implications: mixing sync SQLAlchemy with async FastAPI creates thread-pool bottlenecks. This led to the choice of `create_async_engine` with `aiosqlite`.

- **Q:** *"What is a star schema and is it the right pattern for race results data?"*
  - Claude explained that a fact table (results) with dimension tables (drivers, teams, circuits, races) enables natural GROUP BY aggregations — exactly the pattern needed for analytics. This shaped the entire database design.

### 2. Security Implementation

JWT dual-token authentication and bcrypt hashing were implemented with Claude's guidance:

- **Q:** *"Why use two tokens (access + refresh) instead of one long-lived token?"*
  - Claude explained the security trade-off: a stolen access token with a 30-minute expiry limits damage, while the refresh token stored securely (not sent with every request) is harder to steal. This is the pattern used by Google and GitHub.

- **Q:** *"What is a timing attack and how does it apply to login endpoints?"*
  - Claude explained that if a login handler returns faster for "user not found" vs "wrong password", an attacker can enumerate usernames. Claude suggested the constant-time dummy-hash pattern in `auth_service.py`.

### 3. SQL Analytics Queries

The six analytics queries required non-trivial SQL patterns:

- **Q:** *"How do I count race wins (position = 1) within a GROUP BY query without a subquery?"*
  - Claude introduced `COUNT(CASE WHEN position = 1 THEN 1 END)` — conditional aggregation. This became the core pattern in `analytics_service.py`.

- **Q:** *"How do I join the same table twice in SQLAlchemy to compare two drivers in shared races?"*
  - Claude explained the `aliased()` function, allowing the `results` table to appear twice in the same query as `res_a` and `res_b`. This enabled the head-to-head endpoint.

- **Q:** *"In a head-to-head comparison, how do I handle DNFs correctly so a retired driver 'loses' to a finisher?"*
  - Claude suggested using `position_order` (which ranks all finishers before all retirements) rather than `position` (which is NULL for DNFs). This is a non-obvious but correct data decision.

### 4. Testing Architecture

- **Q:** *"How do I make FastAPI use a different database in tests without changing the application code?"*
  - Claude explained `app.dependency_overrides` — a FastAPI feature that replaces a dependency (like `get_db`) at test time. This is the standard testing pattern for FastAPI and is now in `conftest.py`.

- **Q:** *"What is the difference between pytest fixture scopes (function vs session)?"*
  - Claude explained that `scope="session"` means the fixture runs once for the entire test suite, while `scope="function"` means it runs fresh for every test. The test database is created at session scope; the HTTP client is recreated at function scope.

### 5. MCP Server Design

- **Q:** *"What are the design principles for MCP tool descriptions that make them most useful to an LLM?"*
  - Claude explained that tool descriptions should state preconditions ("use search_drivers first"), parameter semantics, and include concrete examples with expected outputs. This shaped the docstrings in `mcp_server/server.py`.

- **Q:** *"Why add discovery tools (search_drivers, search_circuits) when the user could just know the IDs?"*
  - Claude pointed out that an LLM receiving a natural-language query ("Hamilton's stats") has no way to know the numeric ID without a search step. Discovery tools make the MCP server self-sufficient.

### 6. Debugging

Several errors were diagnosed with Claude's help:

- **bcrypt compatibility:** `passlib 1.7.4` references `bcrypt.__about__` which was removed in `bcrypt 4.1`. Claude identified this as a known incompatibility and recommended pinning `bcrypt==4.0.1` in `requirements.txt`.

- **Ergast CSV null values:** The Ergast dataset uses MySQL-style `\N` for NULL. Claude identified that `safe_int()` only handled `NaN` (pandas) but not the string `"\N"`, and suggested the `NULL_STRINGS` set pattern in `import_data.py`.

- **Pydantic v2 `Optional[date]`:** A `none_required` validation error appeared when serialising `Race` objects. Claude explained this is a known Pydantic v2 behaviour where `Optional[date] = None` can be misinterpreted, and suggested the `model_validator(mode="before")` pattern to coerce `datetime.date` to ISO strings before validation.

---

## Where Author Judgment Shaped Decisions

GenAI was used as a knowledgeable collaborator, not a code generator. The following decisions reflect independent judgment:

1. **Choosing F1 as the domain** — the richness of multi-dimensional F1 data (drivers, teams, circuits, races, results) was assessed as particularly well-suited to demonstrating analytics depth.

2. **Head-to-head as the sixth analytics endpoint** — this was chosen over simpler alternatives (e.g. "top scorers by season") because it produces genuinely interesting insights (e.g. Hamilton led Rosberg 97-64 in their Mercedes years) and demonstrates a self-join SQL pattern not present in the other five endpoints.

3. **Using `cachetools` instead of Redis** — I judged that Redis adds deployment complexity that outweighs its benefits for a single-server PythonAnywhere deployment. Claude confirmed this trade-off when asked, but the decision to keep it simple was mine.

4. **MCP discovery tools** — the decision to include `search_drivers` and `search_circuits` as prerequisite tools (rather than accepting names directly) was based on my assessment that an ID-based system is more reliable and avoids name-matching ambiguity (e.g. "Schumacher" could be Michael or Ralf).

5. **Test seed data design** — the specific choice of 2 drivers × 2 seasons × 2 rounds × deliberate win distributions (Hamilton wins race1+race3, Verstappen wins race2+race4, Hamilton DNF in race4) was designed to exercise every analytics code path with minimal data while keeping assertions maximally specific.

---

## Tools Used

| Tool | Version | Purpose |
|---|---|---|
| Claude (Anthropic) | claude-sonnet-4.6 | Architecture, implementation, debugging, documentation |

No code was copied directly from GenAI output without review and adaptation. All generated suggestions were tested, and several were modified or rejected based on project-specific constraints (e.g. deployment platform, library versions).
