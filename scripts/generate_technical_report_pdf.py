#!/usr/bin/env python3
"""
Generate a formal technical report PDF for the F1 Analytics API coursework.

The report is written as a static artifact suitable for submission. It is
derived from the repository's actual implementation choices rather than being
hand-maintained in a word processor, which keeps the document reproducible.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = ROOT / "docs" / "technical_report.pdf"
sys.path.insert(0, str(ROOT))

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
from scripts.django_openapi import get_django_settings, get_openapi_schema

settings = get_django_settings()

DATASET_FACTS = [
    ("Drivers", "861"),
    ("Teams", "212"),
    ("Circuits", "77"),
    ("Races", "1,125"),
    ("Results", "26,759"),
    ("Coverage", "1950 to 2024"),
]

LAST_TEST_RUN = "manage.py check + pytest + Django acceptance verification passed on 2026-04-21"
LAST_TEST_WARNINGS = (
    "The current Django adapter flow runs cleanly, including shared OpenAPI schema export from the FastAPI core."
)
PUBLIC_GITHUB_REPOSITORY = "https://github.com/BochunYuan/Web-Services-and-Web-Data.git"


def count_test_functions(path: Path) -> int:
    text = path.read_text(encoding="utf-8")
    return len(re.findall(r"^\s*(?:async\s+def|def)\s+test_", text, flags=re.MULTILINE))


def pytest_collected_count() -> int:
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    match = re.search(r"(\d+) tests collected", result.stdout + result.stderr)
    if not match:
        raise RuntimeError("Could not determine pytest collected test count")
    return int(match.group(1))


def api_stats() -> tuple[int, int]:
    openapi = get_openapi_schema()
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
    total_tests = pytest_collected_count()

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
            ("GitHub repository", PUBLIC_GITHUB_REPOSITORY),
            ("Version", settings.PROJECT_VERSION),
            ("API surface", f"{operations} HTTP operations including {analytics} analytics endpoints"),
            ("Test suite", f"{total_tests} automated tests across {len(test_modules)} modules"),
            (
                "Static outputs",
                "docs/api_documentation.pdf, docs/technical_report.pdf, "
                "docs/presentation_slides.pdf, docs/presentation_slides.pptx",
            ),
        ]
    )
    layout.add_paragraph(
        "The project exceeds the coursework minimum by combining CRUD resources, "
        "historical analytics, JWT security, automated tests, generated API "
        "documentation, CSV import tooling, and a WSGI-friendly Django adapter deployment track.",
        size=10.4,
    )

    layout.add_section_heading(
        "Stack Justification",
        "The stack is intentionally API-first. Each dependency reduces boilerplate "
        "or supports a concrete engineering need rather than being included for novelty.",
    )
    layout.add_key_value_list(
        [
            ("FastAPI + Pydantic", "Single source of truth for routing, validation, response models, and OpenAPI generation."),
            ("Django 5.2 adapter", "WSGI-compatible deployment shell for PythonAnywhere-style hosting, static assets, docs entrypoints, and API prefix routing."),
            ("SQLAlchemy + Alembic", "Shared persistence layer and migration story used by the runtime API and data-import tooling."),
            ("SQLite + DATABASE_URL", "SQLite is the verified local database, while DATABASE_URL keeps the deployment configuration portable for a future SQL backend."),
            ("JWT + bcrypt", "Protected write operations use short-lived access tokens, refresh tokens, and safe password hashing."),
            ("collectstatic + static dashboard", "Production static files are collected to STATIC_ROOT while the frontend reads API_V1_PREFIX from Django."),
        ]
    )
    layout.add_bullets(
        [
            "The Django adapter keeps the API-first behaviour while fitting hosts that expect a WSGI application.",
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
            ("f1_django/settings.py", "Loads .env configuration, DATABASE_URL, STATIC_ROOT, and API_V1_PREFIX for the deployment adapter."),
            ("f1_django/urls.py", "Mounts docs, health, static development serving, and the API proxy under the configured prefix."),
            ("django_api/views.py", "Acts as a thin in-process proxy from Django HttpRequest objects to the FastAPI ASGI app."),
            ("app/routers + app/services", "Contain the actual API behaviour, auth flow, CRUD logic, analytics queries, and cache orchestration."),
            ("app/models + app/schemas", "Separate persistence models from public request/response contracts without duplicating implementations across frameworks."),
            ("scripts/verify_django_acceptance.py", "Runs end-to-end checks on a temporary SQLite copy without mutating the main database."),
        ]
    )
    layout.add_bullets(
        [
            "The results table acts as the fact table for analytics, with drivers, teams, races, and circuits as dimensions.",
            "Analytics code uses shared SQLAlchemy query construction, aggregation, joins, distinct counts, and shared-race comparisons for head-to-head analysis.",
            "Caching stays in the FastAPI service layer and invalidates after successful commits, which keeps transport code clean.",
            "The root page injects API_V1_PREFIX so the static frontend follows the same route prefix as the backend.",
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
        "app/services/analytics_service.py implements six analytical queries over "
        "historical race data. The shared FastAPI core uses SQLAlchemy expressions, "
        "conditional aggregation, and focused reshaping in Python rather than raw "
        "SQL strings. This keeps the queries portable while preserving clear analytical behaviour."
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
        "transaction boundary in the runtime implementation. Django now forwards "
        "requests into that same core instead of maintaining a second set of write "
        "handlers, which removes behavioural drift and keeps uniqueness handling in one place."
    )
    layout.add_bullets(
        [
            "Repeated create, update, and delete patterns stay small because generic CRUD helpers and shared schemas are reused across routers.",
            "Database uniqueness is enforced by model constraints and defensive conflict handling in the FastAPI layer.",
            "app/services/cache_service.py defers invalidation until after a successful commit, so failed writes do not evict valid cached analytics responses.",
        ],
        size=9.8,
    )
    layout.add_subheading("Authentication and defensive API behaviour")
    layout.add_paragraph(
        "Authentication is implemented with dual JWT tokens: access tokens protect "
        "write operations and refresh tokens issue replacement access tokens without "
        "forcing a full login. app/services/auth_service.py performs a dummy bcrypt "
        "verification when a username is unknown, while app/core/security.py owns "
        "JWT creation and decoding. Combined with rate limiting and explicit 401 or 403 responses, this "
        "creates a noticeably more mature security story than a coursework API that "
        "only checks a password and returns generic responses."
    )

    layout.add_section_heading(
        "Implementation Challenges",
        "The most meaningful engineering work happened in areas where a simple CRUD scaffold would have been insufficient.",
    )
    layout.add_key_value_list(
        [
            ("Single-source API behaviour", "Django now proxies to the FastAPI app in-process, removing the earlier risk of duplicated endpoint implementations drifting apart."),
            ("Data import cleaning", "scripts/import_data.py normalises Ergast null markers such as \\N and converts numeric, date, and time fields safely."),
            ("Correct analytics logic", "Head-to-head comparisons use position_order instead of finishing position so DNFs are handled fairly."),
            ("Deployment compatibility", "STATIC_ROOT, collectstatic, allowed hosts, and API_V1_PREFIX are configurable for PythonAnywhere-style hosting."),
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
        "Automated verification is one of the strongest parts of the repository. "
        "The Django acceptance script checks behaviour through Django's own test client "
        "rather than relying only on manual browser tests.",
    )
    layout.add_key_value_list(
        [
            ("Latest verification", LAST_TEST_RUN),
            ("Coverage focus", "register, form login, JSON login, refresh, auth/me, drivers, teams, circuits, races, results, analytics, docs, health, frontend, and static assets"),
            ("Isolation strategy", "scripts/verify_django_acceptance.py copies f1_analytics.db into a temporary SQLite file before migrating with --fake-initial."),
            ("Execution style", "Django Client exercises the deployment adapter, authentication, validation, response handling, OpenAPI docs, and static entrypoints in process."),
        ]
    )
    layout.add_bullets(
        [
            "Deterministic seed data keeps analytics assertions specific and explainable.",
            "Authentication tests cover register, login, refresh, protected access, and invalid credentials.",
            "CRUD tests verify pagination, filtering, duplicate handling, and correct 401/404/409/422 responses.",
            "OpenAPI generation is checked directly with scripts/django_openapi.py and through /openapi.json in the acceptance flow.",
            LAST_TEST_WARNINGS,
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
            "SQLite is the verified database for this coursework build; a MySQL deployment would need a matching async SQLAlchemy driver and production-environment validation.",
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
            ("Author judgement", "Domain choice, analytics design, cache trade-offs, deployment adaptation decisions, and seed-data design remained human decisions"),
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
            ("API functionality", "CRUD resources, authentication, results filtering, six analytics endpoints, OpenAPI docs, and static frontend integration."),
            ("Code quality", "Layered settings/urls/views plus routers/services/models/schemas structure with one API implementation, central configuration, and cache invalidation."),
            ("Error handling", "Consistent 401, 404, 409, 422, and 429 responses backed by validation, database constraints, and middleware."),
            ("Testing evidence", "Django system checks, pytest, schema export, and acceptance verification confirm the adapted stack preserves runtime behaviour."),
            ("Originality", "The analytics layer and framework adaptation move the project beyond a standard CRUD API into a deployment-aware sports analysis platform."),
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
