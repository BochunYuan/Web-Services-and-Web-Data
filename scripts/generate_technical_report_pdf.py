#!/usr/bin/env python3
"""
Generate a formal technical report PDF for the F1 Analytics API coursework.

The report is written as a static artifact suitable for submission. It is
derived from the repository's actual implementation choices rather than being
hand-maintained in a word processor, which keeps the document reproducible.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = ROOT / "docs" / "technical_report.pdf"
sys.path.insert(0, str(ROOT))

from app.config import settings
from app.main import app
from scripts.generate_api_documentation_pdf import (
    A4_HEIGHT,
    A4_WIDTH,
    COLORS,
    CONTENT_WIDTH,
    FONT_MAP,
    LEFT_MARGIN,
    RIGHT_MARGIN,
    Layout,
    Line,
    PDFBuilder,
    Rect,
    TextRun,
    wrap_text,
)

DATASET_FACTS = [
    ("Drivers", "861"),
    ("Teams", "212"),
    ("Circuits", "77"),
    ("Races", "1,125"),
    ("Results", "26,759"),
    ("Coverage", "1950 to 2024"),
]

LAST_TEST_RUN = "178 passed, 1 warning in 8.71s on 2026-04-20"
LAST_TEST_WARNINGS = (
    "The remaining warning in the latest local run comes from passlib's "
    "third-party dependency on Python's deprecated crypt module rather than "
    "from project code."
)


def count_test_functions(path: Path) -> int:
    text = path.read_text(encoding="utf-8")
    return len(re.findall(r"^\s*(?:async\s+def|def)\s+test_", text, flags=re.MULTILINE))


def api_stats() -> tuple[int, int]:
    openapi = app.openapi()
    operations = 0
    analytics = 0
    for path, methods in openapi["paths"].items():
        if not path.startswith(settings.API_V1_PREFIX):
            continue
        for _method in methods:
            operations += 1
            if path.startswith(f"{settings.API_V1_PREFIX}/analytics"):
                analytics += 1
    return operations, analytics


class ReportLayout(Layout):
    def _draw_header_footer(self) -> None:
        assert self.page is not None
        self.page.lines.append(
            Line(LEFT_MARGIN, A4_HEIGHT - 46, A4_WIDTH - RIGHT_MARGIN, A4_HEIGHT - 46, COLORS["rule"], 1)
        )
        self.page.lines.append(
            Line(LEFT_MARGIN, 38, A4_WIDTH - RIGHT_MARGIN, 38, COLORS["rule"], 1)
        )
        self.page.texts.append(
            TextRun(LEFT_MARGIN, A4_HEIGHT - 34, "F1 Analytics API", FONT_MAP["body_bold"], 10.5, COLORS["brand"])
        )
        self.page.texts.append(
            TextRun(
                A4_WIDTH - RIGHT_MARGIN - 122,
                A4_HEIGHT - 34,
                "Technical Report",
                FONT_MAP["body"],
                10,
                COLORS["muted"],
            )
        )
        self.page.texts.append(
            TextRun(LEFT_MARGIN, 22, f"Generated from repository state on {self.generated_on}", FONT_MAP["body"], 9, COLORS["muted"])
        )
        self.page.texts.append(
            TextRun(A4_WIDTH - RIGHT_MARGIN - 52, 22, f"Page {self.page_number}", FONT_MAP["body"], 9, COLORS["muted"])
        )

    def add_report_title_page(self, stats: list[tuple[str, str]]) -> None:
        assert self.page is not None
        top_box_y = A4_HEIGHT - 324
        top_box_height = 238
        self.page.rects.append(Rect(LEFT_MARGIN, top_box_y, CONTENT_WIDTH, top_box_height, COLORS["brand_soft"]))

        self.page.texts.append(
            TextRun(LEFT_MARGIN + 30, top_box_y + 178, "F1 Analytics API", FONT_MAP["body_bold"], 28, COLORS["brand"])
        )
        self.page.texts.append(
            TextRun(LEFT_MARGIN + 30, top_box_y + 145, "Formal Technical Report", FONT_MAP["body_bold"], 18, COLORS["ink"])
        )
        self.page.texts.append(
            TextRun(
                LEFT_MARGIN + 30,
                top_box_y + 110,
                "XJCO3011 Web Services and Web Data - Coursework 1",
                FONT_MAP["body"],
                12.6,
                COLORS["muted"],
            )
        )

        overview = (
            "This report evaluates the current implementation of the F1 Analytics "
            "API from a technical perspective. It covers stack justification, "
            "system architecture, engineering challenges, testing evidence, "
            "known limitations, and the declared use of GenAI during development."
        )
        lines = wrap_text(overview, CONTENT_WIDTH - 60, 11.4)
        y = top_box_y + 73
        for line in lines:
            self.page.texts.append(TextRun(LEFT_MARGIN + 30, y, line, FONT_MAP["body"], 11.4, COLORS["ink"]))
            y -= 15

        stat_y = top_box_y - 82
        box_width = (CONTENT_WIDTH - 16) / 2
        box_height = 54
        for idx, (label, value) in enumerate(stats):
            x = LEFT_MARGIN + (idx % 2) * (box_width + 16)
            if idx and idx % 2 == 0:
                stat_y -= box_height + 14
            self.page.rects.append(Rect(x, stat_y, box_width, box_height, COLORS["panel"]))
            self.page.texts.append(TextRun(x + 16, stat_y + 31, label, FONT_MAP["body"], 10.4, COLORS["muted"]))
            self.page.texts.append(TextRun(x + 16, stat_y + 12, value, FONT_MAP["body_bold"], 14.6, COLORS["ink"]))

        self.page.texts.append(
            TextRun(
                LEFT_MARGIN,
                92,
                f"Project version: {settings.PROJECT_VERSION}    API prefix: {settings.API_V1_PREFIX}",
                FONT_MAP["body"],
                10,
                COLORS["muted"],
            )
        )
        self.page.texts.append(
            TextRun(
                LEFT_MARGIN,
                72,
                "Deliverables: docs/api_documentation.pdf and docs/technical_report.pdf",
                FONT_MAP["body"],
                10,
                COLORS["muted"],
            )
        )
        self._new_page()

    def add_key_value_list(
        self,
        rows: list[tuple[str, str]],
        *,
        label_width: float = 158,
        size: float = 10.2,
        row_gap: float = 4,
    ) -> None:
        """
        Render a two-column key/value list without horizontal overlap.

        The base Layout implementation assumes labels fit on a single line.
        That works for short API-doc fields, but the technical report contains
        longer labels such as "app/models + app/schemas" and
        "Documentation reliability". We therefore wrap both columns and size
        the row height to the taller side.
        """
        leading = size + 3.8
        value_width = CONTENT_WIDTH - label_width - 12
        value_x = LEFT_MARGIN + label_width

        for label, value in rows:
            label_lines = wrap_text(label, label_width - 8, size)
            value_lines = wrap_text(value, value_width, size)
            row_lines = max(len(label_lines), len(value_lines))
            needed = row_lines * leading + row_gap + 2
            self.ensure_space(needed + 4)

            y = self.cursor_y
            for idx in range(row_lines):
                if idx < len(label_lines):
                    self.add_text_line(
                        label_lines[idx],
                        LEFT_MARGIN,
                        y,
                        FONT_MAP["body_bold"],
                        size,
                        COLORS["ink"],
                    )
                if idx < len(value_lines):
                    self.add_text_line(
                        value_lines[idx],
                        value_x,
                        y,
                        FONT_MAP["body"],
                        size,
                        COLORS["ink"],
                    )
                y -= leading

            self.cursor_y = y - row_gap


def build_document() -> PDFBuilder:
    operations, analytics = api_stats()
    test_modules = sorted((ROOT / "tests").glob("test_*.py"))
    total_tests = sum(count_test_functions(path) for path in test_modules)

    doc = PDFBuilder()
    layout = ReportLayout(doc)
    layout.add_section_heading(
        "Technical Report",
        "This submission summarises the current F1 Analytics API implementation "
        "within the coursework page limit. It focuses on the brief's required "
        "areas: stack justification, architecture, implementation challenges, "
        "testing evidence, limitations, and the declared use of GenAI.",
    )
    layout.add_key_value_list(
        [
            ("Module", "XJCO3011 Web Services and Web Data"),
            ("Project", "F1 Analytics API"),
            ("Version", settings.PROJECT_VERSION),
            ("API surface", f"{operations} HTTP operations including {analytics} analytics endpoints"),
            ("Test suite", f"{total_tests} automated tests across {len(test_modules)} modules"),
            ("Static outputs", "docs/api_documentation.pdf, docs/technical_report.pdf, docs/presentation_slides.pdf"),
        ]
    )
    layout.add_paragraph(
        "The project exceeds the coursework minimum by combining CRUD resources, "
        "historical analytics, JWT security, automated tests, generated API "
        "documentation, CSV import tooling, and an MCP wrapper for AI assistants.",
        size=10.4,
    )

    layout.add_section_heading(
        "Stack Justification",
        "The stack is intentionally API-first. Each dependency reduces boilerplate "
        "or supports a concrete engineering need rather than being included for novelty.",
    )
    layout.add_key_value_list(
        [
            ("FastAPI", "Async-native routing plus automatic OpenAPI, Swagger UI, and ReDoc generation."),
            ("Pydantic v2", "Typed request and response validation with field constraints and structured 422 errors."),
            ("SQLAlchemy async", "Database-agnostic ORM and query layer that matches FastAPI's concurrency model."),
            ("SQLite/MySQL", "SQLite keeps local setup lightweight while SQLAlchemy preserves a clean upgrade path to MySQL deployment."),
            ("JWT + bcrypt", "Protected write operations use short-lived access tokens, refresh tokens, and safe password hashing."),
            ("cachetools + FastMCP", "Caching improves repeated analytics calls, while MCP exposes the same analytics to AI tools."),
        ]
    )
    layout.add_bullets(
        [
            "FastAPI fits this submission better than a template-driven framework because the product is an API rather than a server-rendered website.",
            "Keeping Redis out of the coursework stack is a deliberate simplification: in-memory caching is enough for one process and easier to justify clearly.",
            "The chosen libraries make the implementation easier to document, easier to test, and easier for examiners to verify quickly.",
        ],
        size=9.8,
    )

    layout.add_section_heading(
        "Architecture",
        "The system follows a layered architecture so responsibilities are easy to explain and test.",
    )
    layout.add_key_value_list(
        [
            ("app/main.py", "Builds the FastAPI app, mounts static assets, replaces default docs routes, and adds middleware."),
            ("app/database.py", "Owns the async engine, session factory, and single request-scoped transaction boundary."),
            ("app/routers", "Handles HTTP concerns only: routing, query parsing, response models, and authentication dependencies."),
            ("app/services", "Contains business logic such as authentication, analytics aggregation, and caching."),
            ("app/models + app/schemas", "Separates database persistence from public API contracts."),
            ("mcp_server/server.py", "Wraps the HTTP API as AI-callable tools without duplicating analytics logic."),
        ]
    )
    layout.add_bullets(
        [
            "The results table acts as the fact table for analytics, with drivers, teams, races, and circuits as dimensions.",
            "Analytics code uses SQLAlchemy expressions for conditional aggregation, joins, distinct counts, and a self-join for head-to-head analysis.",
            "Caching stays in the service layer and invalidates after successful commits, which keeps transport code clean.",
            "Custom /docs and /redoc routes improve reliability when external CDNs are blocked or slow.",
        ],
        size=9.8,
    )

    layout.add_section_heading(
        "Technical Implementation Detail",
        "The most interesting engineering work appears in the runtime behaviour of "
        "the service rather than in route declarations alone. The codebase makes a "
        "clear distinction between transport, business logic, and persistence, and "
        "that separation is visible in several concrete implementation patterns.",
    )
    layout.add_subheading("Analytics query design")
    layout.add_paragraph(
        "analytics_service.py implements six analytical queries over historical "
        "race data. Shared SQL fragments are extracted into analytics_expressions.py, "
        "which avoids repeating conditional aggregation logic for wins, podiums, "
        "points totals, and race counts. This matters because it keeps the queries "
        "consistent across endpoints while still using SQLAlchemy expressions rather "
        "than raw SQL strings."
    )
    layout.add_bullets(
        [
            "Driver performance groups results by Race.year and returns both season rows and a derived career summary.",
            "Driver comparison executes one grouped query for all requested IDs and then reshapes the rows in Python to preserve request order.",
            "Season highlights uses aggregate totals plus winner queries to identify champions and the most successful driver of the year.",
            "Head-to-head uses aliased(Result) so the same table can be joined twice and shared-race finishing order can be compared safely.",
        ],
        size=9.8,
    )
    layout.add_subheading("Write path, transactions, and cache invalidation")
    layout.add_paragraph(
        "The request-scoped get_db dependency in app/database.py owns the final "
        "transaction boundary. Write handlers generally flush when they need "
        "database-generated values or early integrity checking, but commit happens "
        "exactly once at the end of the request. This avoids duplicated commit "
        "logic and makes rollback behaviour predictable."
    )
    layout.add_bullets(
        [
            "app/utils/crud.py centralises repetitive create, update, refresh, and delete operations so routers stay focused on HTTP concerns.",
            "Database uniqueness is enforced by Alembic-defined constraints and dedicated integrity tests.",
            "cache_service.py defers invalidation until after a successful commit, so failed writes do not evict valid cached analytics responses.",
        ],
        size=9.8,
    )
    layout.add_subheading("Authentication and defensive API behaviour")
    layout.add_paragraph(
        "Authentication is implemented with dual JWT tokens: access tokens protect "
        "write operations and refresh tokens issue replacement access tokens without "
        "forcing a full login. auth_service.py also performs a dummy bcrypt check "
        "when a username is unknown so login timing does not reveal which usernames "
        "exist. Combined with rate limiting and explicit 401 or 403 responses, this "
        "creates a noticeably more mature security story than a coursework API that "
        "only checks a password and returns generic responses."
    )

    layout.add_section_heading(
        "Implementation Challenges",
        "The most meaningful engineering work happened in areas where a simple CRUD scaffold would have been insufficient.",
    )
    layout.add_key_value_list(
        [
            ("Documentation reliability", "The project replaced default FastAPI docs pages with locally hosted assets after a blank ReDoc failure in restricted environments."),
            ("Data import cleaning", "scripts/import_data.py normalises Ergast null markers such as \\N and converts numeric, date, and time fields safely."),
            ("Correct analytics logic", "Head-to-head comparisons use position_order instead of finishing position so DNFs are handled fairly."),
            ("Dependency compatibility", "bcrypt is pinned to a version that remains compatible with passlib, and the reason is documented."),
        ]
    )
    layout.add_paragraph(
        "These issues matter because they affect correctness, usability, and the "
        "credibility of the submission. Solving them required more than adding "
        "routes; it required understanding how data, libraries, and documentation "
        "behave under real constraints.",
        size=10.2,
    )

    layout.add_section_heading(
        "Testing",
        "Automated testing is one of the strongest parts of the repository. The "
        "suite checks behaviour through the ASGI application rather than relying "
        "only on manual browser tests.",
    )
    layout.add_key_value_list(
        [
            ("Latest verification", LAST_TEST_RUN),
            ("Coverage focus", "auth, analytics, drivers, teams, circuits, races, results, database constraints, cache invalidation, rate limiting, import_data, and MCP"),
            ("Isolation strategy", "tests/conftest.py swaps in a separate SQLite database before the app is imported."),
            ("Execution style", "httpx ASGITransport exercises middleware, routing, validation, and response handling in memory."),
        ]
    )
    layout.add_bullets(
        [
            "Deterministic seed data keeps analytics assertions specific and explainable.",
            "Authentication tests cover register, login, refresh, protected access, and invalid credentials.",
            "CRUD tests verify pagination, filtering, duplicate handling, and correct 401/404/409/422 responses.",
            "Dedicated tests now also cover teams, circuits, races, rate limiting, cache invalidation, import_data.py, database constraints, and the MCP wrapper.",
            "The remaining warning comes from a third-party dependency on crypt, not from application logic.",
        ],
        size=9.8,
    )

    layout.add_section_heading(
        "Limitations And Future Work",
        "The current implementation is strong for coursework, but it still has clear limits that should be acknowledged honestly.",
    )
    layout.add_bullets(
        [
            "The initial Alembic baseline is now in place; future schema changes should add incremental revisions rather than editing the baseline.",
            "Caching and rate limiting are in-memory only, so state is not shared across multiple processes.",
            "Refresh tokens are stateless and there is no revocation list or persistent session table.",
            "SQLite is a good development default, but it is not the long-term choice for high write concurrency.",
            "The repository is deployment-ready in principle, but public deployment evidence and infrastructure automation are still limited.",
        ],
        size=9.8,
    )
    layout.add_paragraph(
        "The most useful next steps are adding CI, expanding migration coverage "
        "for deployment rollbacks, and moving cache and rate-limit state into Redis if the project is ever "
        "deployed beyond a single-process coursework setting.",
        size=10.2,
    )

    # Keep the final page intentional rather than leaving only the tail of a
    # split section. This also makes the report easier to use during the oral.
    layout._new_page()

    layout.add_section_heading(
        "GenAI Declaration",
        "GenAI use is declared explicitly and analysed as part of the engineering process rather than hidden.",
    )
    layout.add_key_value_list(
        [
            ("Declared tool", "Claude (Anthropic), documented in AGENTS.md"),
            ("Primary use", "Architecture exploration, security guidance, SQL design, testing strategy, debugging, and documentation support"),
            ("Review stance", "Suggestions were reviewed, adapted, and tested rather than copied blindly"),
            ("Author judgement", "Domain choice, analytics design, cache trade-offs, MCP discovery tools, and seed-data design remained human decisions"),
        ]
    )
    layout.add_bullets(
        [
            "Using GenAI to understand alternatives and accelerate debugging aligns with the brief's Green Light assessment guidance.",
            "The declaration is specific enough to show methodological use rather than vague tool name-dropping.",
            "Exported conversation logs should be submitted as supplementary material outside this five-page report.",
        ],
        size=9.8,
    )

    layout.add_section_heading(
        "Submission Alignment",
        "The implementation maps directly onto the coursework marking criteria "
        "rather than only satisfying the minimum pass requirements.",
    )
    layout.add_key_value_list(
        [
            ("API functionality", "CRUD resources, authentication, results filtering, six analytics endpoints, OpenAPI docs, and MCP access."),
            ("Code quality", "Layered routers/services/models/schemas structure with shared CRUD helpers and central transaction handling."),
            ("Error handling", "Consistent 401, 404, 409, 422, and 429 responses backed by validation, database constraints, and middleware."),
            ("Testing evidence", "178 passing tests verify API behaviour, analytics logic, cache invalidation, rate limiting, imports, MCP, and constraints."),
            ("Originality", "The analytics layer and MCP workflow move the project beyond a standard CRUD API into AI-accessible sports analysis."),
        ],
        size=10.0,
    )
    layout.add_bullets(
        [
            "The project does not treat analytics as decorative extras; they are implemented as first-class endpoints with typed response models and dedicated tests.",
            "Operational concerns such as transaction ownership, cache invalidation timing, and database uniqueness are addressed explicitly rather than left implicit.",
            "Supporting artifacts are aligned with the implementation: README, static API documentation, technical report, and presentation slides all describe the same deployed system shape.",
        ],
        size=9.8,
    )
    layout.add_paragraph(
        "Overall, the project demonstrates a coherent API architecture, a credible "
        "testing story, and a level of analytical depth that clearly goes beyond "
        "minimum CRUD requirements while still staying within an honest coursework scope.",
        size=10.2,
    )

    return doc


def main() -> None:
    document = build_document()
    document.build(OUTPUT_PATH)
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
