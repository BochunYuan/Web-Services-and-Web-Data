#!/usr/bin/env python3
"""
Generate presentation slides for the F1 Analytics API coursework.

The deck is intentionally generated from code so it remains reproducible and
does not depend on PowerPoint, Keynote, or external PDF libraries. Diagrams and
demo panels are drawn directly into the PDF as vector slide elements.
"""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = ROOT / "docs" / "presentation_slides.pdf"
sys.path.insert(0, str(ROOT))

from scripts.generate_api_documentation_pdf import clean_text, escape_pdf_text, wrap_text
from scripts.django_openapi import get_django_settings, get_openapi_schema

settings = get_django_settings()

SLIDE_W = 960.0
SLIDE_H = 540.0
MARGIN = 48.0

COLORS = {
    "bg": (0.035, 0.039, 0.055),
    "bg2": (0.055, 0.059, 0.080),
    "panel": (0.090, 0.098, 0.130),
    "panel2": (0.120, 0.130, 0.170),
    "ink": (0.950, 0.960, 0.980),
    "muted": (0.650, 0.680, 0.740),
    "soft": (0.430, 0.470, 0.540),
    "line": (0.230, 0.250, 0.310),
    "red": (0.882, 0.024, 0.000),
    "red2": (0.650, 0.020, 0.010),
    "gold": (0.960, 0.640, 0.140),
    "green": (0.140, 0.760, 0.380),
    "blue": (0.220, 0.500, 0.900),
    "cyan": (0.150, 0.700, 0.820),
    "purple": (0.440, 0.330, 0.820),
    "white": (1.000, 1.000, 1.000),
    "black": (0.000, 0.000, 0.000),
}

FONTS = {
    "body": "F1",
    "bold": "F2",
    "mono": "F3",
    "mono_bold": "F4",
}


@dataclass
class Text:
    x: float
    y: float
    text: str
    font: str
    size: float
    color: tuple[float, float, float]


@dataclass
class Rect:
    x: float
    y: float
    w: float
    h: float
    fill: tuple[float, float, float]
    stroke: tuple[float, float, float] | None = None
    lw: float = 1.0


@dataclass
class Line:
    x1: float
    y1: float
    x2: float
    y2: float
    color: tuple[float, float, float]
    lw: float = 1.0


@dataclass
class Poly:
    points: list[tuple[float, float]]
    fill: tuple[float, float, float]


@dataclass
class Slide:
    texts: list[Text] = field(default_factory=list)
    rects: list[Rect] = field(default_factory=list)
    lines: list[Line] = field(default_factory=list)
    polys: list[Poly] = field(default_factory=list)


class PDFDeck:
    def __init__(self) -> None:
        self.slides: list[Slide] = []

    def build(self, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        objects: list[bytes] = []

        def add(payload: bytes) -> int:
            objects.append(payload)
            return len(objects)

        f1 = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
        f2 = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>")
        f3 = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier /Encoding /WinAnsiEncoding >>")
        f4 = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier-Bold /Encoding /WinAnsiEncoding >>")

        page_ids: list[int] = []
        pending: list[dict[str, int]] = []
        for slide in self.slides:
            stream = self.render_slide(slide).encode("latin-1", errors="replace")
            content_id = add(f"<< /Length {len(stream)} >>\nstream\n".encode("latin-1") + stream + b"\nendstream")
            page_id = add(b"<< >>")
            page_ids.append(page_id)
            pending.append({"page": page_id, "content": content_id})

        kids = " ".join(f"{page_id} 0 R" for page_id in page_ids)
        pages_id = add(f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>".encode("latin-1"))

        for item in pending:
            payload = (
                f"<< /Type /Page /Parent {pages_id} 0 R "
                f"/MediaBox [0 0 {SLIDE_W:.2f} {SLIDE_H:.2f}] "
                f"/Resources << /Font << /F1 {f1} 0 R /F2 {f2} 0 R /F3 {f3} 0 R /F4 {f4} 0 R >> >> "
                f"/Contents {item['content']} 0 R >>"
            ).encode("latin-1")
            objects[item["page"] - 1] = payload

        catalog_id = add(f"<< /Type /Catalog /Pages {pages_id} 0 R >>".encode("latin-1"))

        buffer = bytearray()
        buffer.extend(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offsets = [0]
        for object_id, payload in enumerate(objects, start=1):
            offsets.append(len(buffer))
            buffer.extend(f"{object_id} 0 obj\n".encode("latin-1"))
            buffer.extend(payload)
            buffer.extend(b"\nendobj\n")

        xref = len(buffer)
        buffer.extend(f"xref\n0 {len(objects) + 1}\n".encode("latin-1"))
        buffer.extend(b"0000000000 65535 f \n")
        for offset in offsets[1:]:
            buffer.extend(f"{offset:010d} 00000 n \n".encode("latin-1"))
        buffer.extend(
            (
                f"trailer\n<< /Size {len(objects) + 1} /Root {catalog_id} 0 R >>\n"
                f"startxref\n{xref}\n%%EOF\n"
            ).encode("latin-1")
        )
        output_path.write_bytes(buffer)

    @staticmethod
    def is_background_rect(rect: Rect) -> bool:
        return (
            (rect.x <= 0.1 and rect.y <= 0.1 and rect.w >= SLIDE_W - 0.1 and rect.h >= SLIDE_H - 0.1)
            or (rect.x <= 0.1 and rect.y <= 0.1 and rect.w <= 14 and rect.h >= SLIDE_H - 0.1)
            or (rect.x >= 740 and rect.y >= 350 and rect.w >= 180 and rect.h >= 160)
        )

    def render_rect(self, rect: Rect) -> list[str]:
        commands = [
            f"{rect.fill[0]:.3f} {rect.fill[1]:.3f} {rect.fill[2]:.3f} rg "
            f"{rect.x:.2f} {rect.y:.2f} {rect.w:.2f} {rect.h:.2f} re f"
        ]
        if rect.stroke:
            commands.append(
                f"{rect.stroke[0]:.3f} {rect.stroke[1]:.3f} {rect.stroke[2]:.3f} RG "
                f"{rect.lw:.2f} w {rect.x:.2f} {rect.y:.2f} {rect.w:.2f} {rect.h:.2f} re S"
            )
        return commands

    def render_slide(self, slide: Slide) -> str:
        commands: list[str] = []
        background_rects = [rect for rect in slide.rects if self.is_background_rect(rect)]
        foreground_rects = [rect for rect in slide.rects if not self.is_background_rect(rect)]

        for rect in background_rects:
            commands.extend(self.render_rect(rect))
        for poly in slide.polys:
            if not poly.points:
                continue
            first = poly.points[0]
            path = [f"{first[0]:.2f} {first[1]:.2f} m"]
            for point in poly.points[1:]:
                path.append(f"{point[0]:.2f} {point[1]:.2f} l")
            commands.append(
                f"{poly.fill[0]:.3f} {poly.fill[1]:.3f} {poly.fill[2]:.3f} rg "
                + " ".join(path)
                + " h f"
            )
        for line in slide.lines:
            commands.append(
                f"{line.color[0]:.3f} {line.color[1]:.3f} {line.color[2]:.3f} RG "
                f"{line.lw:.2f} w {line.x1:.2f} {line.y1:.2f} m {line.x2:.2f} {line.y2:.2f} l S"
            )
        for rect in foreground_rects:
            commands.extend(self.render_rect(rect))
        for text in slide.texts:
            cleaned = clean_text(text.text)
            commands.append(
                "BT "
                f"/{text.font} {text.size:.2f} Tf "
                f"{text.color[0]:.3f} {text.color[1]:.3f} {text.color[2]:.3f} rg "
                f"1 0 0 1 {text.x:.2f} {text.y:.2f} Tm "
                f"({escape_pdf_text(cleaned)}) Tj ET"
            )
        return "\n".join(commands)


class Canvas:
    def __init__(self, deck: PDFDeck, title: str, subtitle: str | None = None, number: int = 1) -> None:
        self.deck = deck
        self.slide = Slide()
        self.deck.slides.append(self.slide)
        self.number = number
        self.bg()
        if title:
            self.title(title, subtitle)
        self.footer()

    def bg(self) -> None:
        self.rect(0, 0, SLIDE_W, SLIDE_H, COLORS["bg"])
        self.rect(0, 0, SLIDE_W, 540, (0.045, 0.047, 0.067))
        self.rect(0, 0, 12, SLIDE_H, COLORS["red"])
        self.rect(760, 360, SLIDE_W - 760, 180, (0.080, 0.030, 0.035))
        self.line(MARGIN, 52, SLIDE_W - MARGIN, 52, COLORS["line"], 1)

    def footer(self) -> None:
        self.text(MARGIN, 24, "F1 Analytics API", 9.5, COLORS["muted"], bold=True)
        self.text(SLIDE_W - 120, 24, f"{self.number:02d}", 9.5, COLORS["muted"])

    def title(self, title: str, subtitle: str | None = None) -> None:
        self.text(MARGIN, 492, title, 28, COLORS["ink"], bold=True)
        if subtitle:
            self.text(MARGIN, 468, subtitle, 12.5, COLORS["muted"])
        self.line(MARGIN, 452, MARGIN + 132, 452, COLORS["red"], 3)

    def text(
        self,
        x: float,
        y: float,
        text: str,
        size: float,
        color: tuple[float, float, float] = COLORS["ink"],
        *,
        bold: bool = False,
        mono: bool = False,
    ) -> None:
        font = FONTS["mono_bold" if mono and bold else "mono" if mono else "bold" if bold else "body"]
        self.slide.texts.append(Text(x, y, text, font, size, color))

    def text_width(self, text: str, size: float, *, mono: bool = False) -> float:
        factor = 0.62 if mono else 0.54
        return len(text) * size * factor

    def center_text(
        self,
        x: float,
        y: float,
        w: float,
        text: str,
        size: float,
        color: tuple[float, float, float] = COLORS["ink"],
        *,
        bold: bool = False,
        mono: bool = False,
    ) -> None:
        tx = x + max(0, (w - self.text_width(text, size, mono=mono)) / 2)
        self.text(tx, y, text, size, color, bold=bold, mono=mono)

    def paragraph(
        self,
        x: float,
        y: float,
        text: str,
        width: float,
        size: float = 12,
        color: tuple[float, float, float] = COLORS["ink"],
        *,
        leading: float | None = None,
        bold: bool = False,
    ) -> float:
        leading = leading or size + 5
        lines = wrap_text(text, width, size)
        cy = y
        for line in lines:
            self.text(x, cy, line, size, color, bold=bold)
            cy -= leading
        return cy

    def bullets(self, x: float, y: float, items: list[str], width: float, size: float = 12) -> float:
        cy = y
        for item in items:
            lines = wrap_text(item, width - 22, size)
            self.text(x, cy, "-", size + 2, COLORS["red"], bold=True)
            self.text(x + 20, cy, lines[0], size, COLORS["ink"])
            cy -= size + 5
            for line in lines[1:]:
                self.text(x + 20, cy, line, size, COLORS["ink"])
                cy -= size + 5
            cy -= 5
        return cy

    def rect(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        fill: tuple[float, float, float],
        stroke: tuple[float, float, float] | None = None,
        lw: float = 1.0,
    ) -> None:
        self.slide.rects.append(Rect(x, y, w, h, fill, stroke, lw))

    def line(self, x1: float, y1: float, x2: float, y2: float, color: tuple[float, float, float], lw: float = 1.0) -> None:
        self.slide.lines.append(Line(x1, y1, x2, y2, color, lw))

    def arrow(self, x1: float, y1: float, x2: float, y2: float, color: tuple[float, float, float] = COLORS["red"], lw: float = 2.0) -> None:
        self.line(x1, y1, x2, y2, color, lw)
        if abs(x2 - x1) >= abs(y2 - y1):
            direction = 1 if x2 >= x1 else -1
            self.slide.polys.append(
                Poly([(x2, y2), (x2 - 12 * direction, y2 + 6), (x2 - 12 * direction, y2 - 6)], color)
            )
        else:
            direction = 1 if y2 >= y1 else -1
            self.slide.polys.append(
                Poly([(x2, y2), (x2 - 6, y2 - 12 * direction), (x2 + 6, y2 - 12 * direction)], color)
            )

    def card(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        title: str,
        body: str,
        accent: tuple[float, float, float] = COLORS["red"],
        *,
        title_size: float = 14.2,
        body_size: float = 11.0,
        pad: float = 16,
    ) -> None:
        self.rect(x, y, w, h, COLORS["panel"], COLORS["line"], 1)
        self.rect(x, y + h - 5, w, 5, accent)
        self.text(x + pad, y + h - max(25, h * 0.26), title, title_size, COLORS["ink"], bold=True)
        self.paragraph(
            x + pad,
            y + h - max(48, h * 0.50),
            body,
            w - pad * 2,
            body_size,
            COLORS["muted"],
            leading=body_size + 4.2,
        )

    def stat(
        self,
        x: float,
        y: float,
        w: float,
        label: str,
        value: str,
        color: tuple[float, float, float] = COLORS["red"],
        *,
        h: float = 74,
        value_size: float = 23,
        label_size: float = 10.8,
    ) -> None:
        self.rect(x, y, w, h, COLORS["panel"], COLORS["line"], 1)
        self.center_text(x, y + h * 0.60, w, value, value_size, color, bold=True)
        self.center_text(x, y + h * 0.33, w, label, label_size, COLORS["muted"])

    def browser_frame(self, x: float, y: float, w: float, h: float, url: str) -> None:
        self.rect(x, y, w, h, COLORS["panel"], COLORS["line"], 1)
        self.rect(x, y + h - 34, w, 34, COLORS["panel2"])
        self.rect(x + 14, y + h - 22, 8, 8, COLORS["red"])
        self.rect(x + 30, y + h - 22, 8, 8, COLORS["gold"])
        self.rect(x + 46, y + h - 22, 8, 8, COLORS["green"])
        self.rect(x + 72, y + h - 25, w - 92, 14, COLORS["bg2"], COLORS["line"], 0.5)
        self.text(x + 82, y + h - 22, url, 7.8, COLORS["muted"], mono=True)


def count_tests(path: str) -> int:
    text = (ROOT / path).read_text(encoding="utf-8")
    return len(re.findall(r"^\s*(?:async\s+def|def)\s+test_", text, re.MULTILINE))


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


def line_count(path: str) -> int:
    return sum(1 for _ in (ROOT / path).read_text(encoding="utf-8").splitlines())


def test_inventory() -> dict[str, int]:
    return {
        "auth": count_tests("tests/test_auth.py"),
        "analytics": count_tests("tests/test_analytics.py"),
        "resource_api": (
            count_tests("tests/test_drivers.py")
            + count_tests("tests/test_teams.py")
            + count_tests("tests/test_circuits.py")
            + count_tests("tests/test_races.py")
            + count_tests("tests/test_results.py")
        ),
        "infra_import": (
            count_tests("tests/test_cache_invalidation.py")
            + count_tests("tests/test_database_constraints.py")
            + count_tests("tests/test_database_migrations.py")
            + count_tests("tests/test_import_data.py")
            + count_tests("tests/test_rate_limiter.py")
        ),
        "platform": count_tests("tests/test_mcp_server.py"),
    }


def api_counts() -> tuple[int, int]:
    schema = get_openapi_schema()
    operations = 0
    analytics = 0
    for path, methods in schema["paths"].items():
        if not path.startswith(settings.API_V1_PREFIX):
            continue
        for _method in methods:
            operations += 1
            if path.startswith(f"{settings.API_V1_PREFIX}/analytics"):
                analytics += 1
    return operations, analytics


def table_box(c: Canvas, x: float, y: float, w: float, h: float, name: str, fields: list[str], color: tuple[float, float, float]) -> None:
    c.rect(x, y, w, h, COLORS["panel"], COLORS["line"], 1)
    header_h = 32
    c.rect(x, y + h - header_h, w, header_h, color)
    c.text(x + 14, y + h - 22, name, 13.5, COLORS["white"], bold=True)
    fy = y + h - header_h - 16
    for field in fields[:7]:
        c.text(x + 14, fy, field, 9.2, COLORS["muted"], mono=True)
        fy -= 14.5


def add_title_slide(deck: PDFDeck, number: int, operations: int, analytics: int) -> None:
    c = Canvas(deck, "", number=number)
    c.text(72, 382, "F1 Analytics API", 42, COLORS["ink"], bold=True)
    c.text(72, 338, "Presentation Slides", 25, COLORS["red"], bold=True)
    c.paragraph(
        72,
        300,
        "A RESTful Formula 1 data platform with a single FastAPI core, plus a thin Django adapter for WSGI deployment, static frontend parity, and coursework-ready documentation.",
        575,
        15,
        COLORS["muted"],
        leading=21,
    )
    c.stat(72, 164, 142, "Drivers", "861", COLORS["red"], h=82, value_size=20.5, label_size=11.2)
    c.stat(232, 164, 142, "Teams", "212", COLORS["gold"], h=82, value_size=20.5, label_size=11.2)
    c.stat(392, 164, 142, "Results", "26,759", COLORS["green"], h=82, value_size=19.0, label_size=11.2)
    c.stat(552, 164, 142, "OpenAPI ops", str(operations), COLORS["cyan"], h=82, value_size=20.5, label_size=11.2)
    c.stat(712, 164, 142, "Analytics", str(analytics), COLORS["purple"], h=82, value_size=20.5, label_size=11.2)
    c.rect(710, 276, 160, 128, COLORS["panel"], COLORS["line"], 1)
    c.center_text(710, 374, 160, "Stack", 13.8, COLORS["ink"], bold=True)
    c.text(732, 344, "Django 5.2", 11.8, COLORS["muted"])
    c.text(732, 322, "FastAPI + Pydantic", 9.8, COLORS["muted"])
    c.text(732, 300, "JWT + bcrypt", 11.8, COLORS["muted"])
    c.text(732, 278, "collectstatic", 11.8, COLORS["muted"])


def add_scope_slide(deck: PDFDeck, number: int) -> None:
    c = Canvas(deck, "Submission Snapshot", "What the current codebase now delivers", number)
    c.card(64, 330, 250, 95, "Single API core", "FastAPI owns auth, CRUD, results, analytics, OpenAPI generation, and cache invalidation as the single source of truth.", COLORS["red"])
    c.card(354, 330, 250, 95, "Django adapter", "Django serves root, docs, health, static assets, and proxies API requests in-process without duplicating business logic.", COLORS["gold"])
    c.card(644, 330, 250, 95, "Domain coverage", "Drivers, teams, circuits, and races support authenticated CRUD; results stay read-only because they are historical source data.", COLORS["green"])
    c.card(64, 190, 250, 95, "Analytics depth", "Six endpoints compute season highlights, team standings, circuit history, driver comparison, and head-to-head performance.", COLORS["cyan"])
    c.card(354, 190, 250, 95, "Security baseline", "JWT access and refresh tokens, bcrypt hashing, active-user guards, explicit CORS, and per-IP rate limiting.", COLORS["purple"])
    c.card(644, 190, 250, 95, "Artifacts", "Swagger UI, ReDoc, OpenAPI JSON, frontend dashboard, PDF documentation, technical report, and this regenerated PPTX.", COLORS["blue"])
    c.paragraph(
        70,
        116,
        "Design focus: a coursework-sized system that stays layered, testable, and submission-ready while removing the earlier duplicate-stack maintenance risk.",
        810,
        13,
        COLORS["muted"],
    )


def add_refactor_slide(deck: PDFDeck, number: int, operations: int, total_tests: int) -> None:
    c = Canvas(deck, "Code Quality Refactor", "How the current implementation removed the earlier maintainability deductions", number)
    views_lines = line_count("django_api/views.py")
    c.stat(72, 330, 170, "API core", "1", COLORS["red"], h=84, value_size=25.0, label_size=11.8)
    c.stat(266, 330, 170, "OpenAPI ops", str(operations), COLORS["gold"], h=84, value_size=24.0, label_size=11.8)
    c.stat(460, 330, 170, "Proxy lines", str(views_lines), COLORS["green"], h=84, value_size=24.0, label_size=11.8)
    c.stat(654, 330, 170, "Automated tests", str(total_tests), COLORS["cyan"], h=84, value_size=24.0, label_size=11.8)

    c.rect(72, 136, 378, 144, COLORS["panel"], COLORS["line"], 1)
    c.text(94, 246, "Removed Risks", 15, COLORS["ink"], bold=True)
    c.bullets(
        94,
        218,
        [
            "No second Django business stack to drift away from the FastAPI implementation.",
            "No large duplicated CRUD/auth view layer in django_api/views.py.",
            "No separate schema/documentation path that can fall out of sync with runtime behaviour.",
        ],
        324,
        10.8,
    )

    c.rect(510, 136, 378, 144, COLORS["panel"], COLORS["line"], 1)
    c.text(532, 246, "Current Shape", 15, COLORS["ink"], bold=True)
    c.bullets(
        532,
        218,
        [
            "django_api/views.py is now a thin in-process proxy to app.main:app.",
            "Django and FastAPI share DATABASE_URL normalization and the same OpenAPI schema source.",
            "Docs, acceptance checks, README, report, and slides now all describe the same architecture.",
        ],
        324,
        10.8,
    )

    c.paragraph(
        74,
        106,
        "Core message: the refactor did not just tidy naming. It removed duplicated runtime responsibilities and made the deployed behaviour easier to reason about, document, and verify.",
        814,
        12.5,
        COLORS["muted"],
    )


def add_architecture_slide(deck: PDFDeck, number: int) -> None:
    c = Canvas(deck, "Architecture Diagram", "Single FastAPI core with a thin Django deployment adapter", number)
    c.card(60, 345, 170, 70, "Frontend UI", "Static HTML/CSS/JS dashboard served from /static.", COLORS["red"])
    c.card(60, 245, 170, 70, "Docs surface", "Swagger UI, ReDoc, and OpenAPI JSON.", COLORS["gold"])
    c.card(60, 145, 170, 70, "Direct ASGI dev", "uvicorn app.main:app --reload uses the same API core directly.", COLORS["purple"])

    c.card(300, 360, 190, 82, "Django adapter", "f1_django/settings.py and urls.py expose WSGI hosting, static files, docs, health, and API prefix routing.", COLORS["cyan"])
    c.card(300, 250, 190, 82, "Proxy layer", "django_api/views.py forwards Django requests in-process to app.main:app.", COLORS["blue"])
    c.card(300, 140, 190, 82, "FastAPI routers", "auth, drivers, teams, circuits, races, results, and analytics live in one implementation.", COLORS["green"])

    c.card(560, 360, 170, 82, "Services", "auth_service, analytics_service, and cache_service centralise behaviour behind the routers.", COLORS["red"])
    c.card(560, 250, 170, 82, "Schemas + models", "Pydantic schemas and SQLAlchemy models define contracts and persistence once.", COLORS["gold"])
    c.card(560, 140, 170, 82, "Runtime guarantees", "OpenAPI, auth flow, and CRUD semantics come from the same FastAPI core in every mode.", COLORS["purple"])

    c.card(790, 305, 120, 72, "SQLite verified", "Local and acceptance DB", COLORS["green"])
    c.card(790, 205, 120, 72, "Portable DB URL", "Future SQL backend path", COLORS["blue"])

    for y in [380, 280, 180]:
        c.arrow(230, y, 300, y, COLORS["red"], 2)
    c.arrow(490, 400, 560, 400, COLORS["cyan"], 2)
    c.arrow(490, 290, 560, 290, COLORS["cyan"], 2)
    c.arrow(490, 180, 560, 180, COLORS["cyan"], 2)
    c.arrow(730, 290, 790, 340, COLORS["gold"], 2)
    c.arrow(730, 290, 790, 240, COLORS["gold"], 2)
    c.arrow(645, 140, 645, 115, COLORS["purple"], 2)
    c.text(560, 98, "Same FastAPI behaviour through direct ASGI use or the Django WSGI adapter", 9.8, COLORS["muted"])


def add_database_slide(deck: PDFDeck, number: int) -> None:
    c = Canvas(deck, "Database Diagram", "Star-schema style analytics around the results fact table", number)
    table_box(c, 388, 212, 190, 182, "results", ["id PK", "race_id FK", "driver_id FK", "constructor_id FK", "position", "position_order", "points"], COLORS["red"])
    table_box(c, 82, 315, 180, 130, "drivers", ["id PK", "driver_ref UNIQUE", "forename", "surname INDEX", "nationality INDEX", "code"], COLORS["blue"])
    table_box(c, 82, 125, 180, 130, "teams", ["id PK", "constructor_ref UNIQUE", "name INDEX", "nationality", "url"], COLORS["purple"])
    table_box(c, 700, 315, 180, 130, "races", ["id PK", "year INDEX", "round", "circuit_id FK", "name", "date"], COLORS["green"])
    table_box(c, 700, 125, 180, 130, "circuits", ["id PK", "circuit_ref UNIQUE", "name", "location", "country INDEX", "lat / lng"], COLORS["gold"])
    table_box(c, 388, 70, 190, 110, "users", ["id PK", "username UNIQUE", "email UNIQUE", "hashed_password", "is_active"], COLORS["cyan"])

    c.arrow(262, 370, 388, 315, COLORS["blue"], 2)
    c.arrow(262, 190, 388, 260, COLORS["purple"], 2)
    c.arrow(700, 370, 578, 315, COLORS["green"], 2)
    c.arrow(790, 315, 790, 255, COLORS["gold"], 2)
    c.rect(296, 358, 94, 24, COLORS["bg"])
    c.center_text(296, 366, 94, "1 driver -> many", 8.9, COLORS["muted"])
    c.rect(296, 178, 92, 24, COLORS["bg"])
    c.center_text(296, 186, 92, "1 team -> many", 8.9, COLORS["muted"])
    c.rect(588, 358, 90, 24, COLORS["bg"])
    c.center_text(588, 366, 90, "1 race -> many", 8.9, COLORS["muted"])
    c.rect(805, 280, 82, 34, COLORS["bg"])
    c.center_text(805, 296, 82, "1 circuit", 8.8, COLORS["muted"])
    c.center_text(805, 284, 82, "-> many races", 8.8, COLORS["muted"])
    c.paragraph(
        82,
        96,
        "Analytics joins through results to calculate points, wins, DNFs, champions and head-to-head outcomes.",
        270,
        10.2,
        COLORS["muted"],
    )


def add_security_slide(deck: PDFDeck, number: int) -> None:
    c = Canvas(deck, "Security And Request Flow", "JWT auth, validation, rate limiting and safe password storage", number)
    c.card(70, 338, 190, 88, "Register/login", "Validate credentials, then issue tokens through auth_service.", COLORS["red"], body_size=10.5)
    c.card(305, 338, 190, 88, "bcrypt hash", "Passwords are stored as bcrypt hashes, never plain text.", COLORS["gold"], body_size=10.5)
    c.card(540, 338, 190, 88, "Token pair", "Access token: 30 minutes. Refresh token: 7 days.", COLORS["green"], body_size=10.5)
    c.card(305, 196, 190, 88, "Protected writes", "POST, PUT and DELETE require an active authenticated user.", COLORS["cyan"], body_size=10.5)
    c.card(540, 196, 190, 88, "Rate limit", "Sliding-window per-IP limiter returns 429 with Retry-After.", COLORS["purple"], body_size=10.5)
    c.card(70, 196, 190, 88, "CORS", "Explicit allowed origins, not wildcard browser access.", COLORS["blue"], body_size=10.5)
    c.arrow(260, 380, 305, 380, COLORS["red"], 2)
    c.arrow(495, 380, 540, 380, COLORS["red"], 2)
    c.arrow(635, 340, 635, 285, COLORS["green"], 2)
    c.arrow(540, 245, 495, 245, COLORS["cyan"], 2)
    c.arrow(305, 245, 260, 245, COLORS["cyan"], 2)
    c.rect(770, 182, 120, 238, COLORS["panel"], COLORS["line"], 1)
    c.center_text(770, 390, 120, "Status codes", 13.6, COLORS["ink"], bold=True)
    c.center_text(770, 356, 120, "401 invalid", 9.2, COLORS["muted"], mono=True)
    c.center_text(770, 332, 120, "403 inactive", 9.2, COLORS["muted"], mono=True)
    c.center_text(770, 308, 120, "409 conflict", 9.2, COLORS["muted"], mono=True)
    c.center_text(770, 284, 120, "422 validation", 9.2, COLORS["muted"], mono=True)
    c.center_text(770, 260, 120, "429 rate limit", 9.2, COLORS["muted"], mono=True)
    c.paragraph(72, 126, "Important detail: dummy bcrypt hashing reduces username-enumeration timing risk during login.", 790, 12.8, COLORS["muted"])


def add_frontend_demo_slide(deck: PDFDeck, number: int) -> None:
    c = Canvas(deck, "Docs And Frontend", "User-facing entrypoints served through the current adapter architecture", number)
    c.browser_frame(62, 105, 398, 330, "http://127.0.0.1:8000/")
    c.rect(62, 105, 398, 296, (0.040, 0.042, 0.058))
    c.text(92, 365, "F1 Analytics API", 27, COLORS["ink"], bold=True)
    c.text(92, 333, "Formula 1 Analytics API", 18, COLORS["red"], bold=True)
    c.paragraph(92, 304, "Query race results, driver careers, team championships and head-to-head records across Formula 1 history.", 310, 10.5, COLORS["muted"], leading=14)
    c.rect(92, 250, 300, 38, COLORS["panel"], COLORS["line"], 1)
    c.text(110, 264, "Search a driver - Hamilton", 10, COLORS["muted"])
    c.rect(92, 172, 90, 56, COLORS["panel2"], COLORS["line"], 1)
    c.text(110, 203, "861", 15.5, COLORS["red"], bold=True)
    c.text(110, 185, "Drivers", 8.2, COLORS["muted"])
    c.rect(196, 172, 90, 56, COLORS["panel2"], COLORS["line"], 1)
    c.text(214, 203, "212", 15.5, COLORS["gold"], bold=True)
    c.text(214, 185, "Teams", 8.2, COLORS["muted"])
    c.rect(300, 172, 90, 56, COLORS["panel2"], COLORS["line"], 1)
    c.text(318, 203, "77", 15.5, COLORS["green"], bold=True)
    c.text(318, 185, "Circuits", 8.2, COLORS["muted"])

    c.browser_frame(500, 105, 398, 330, "http://127.0.0.1:8000/#explore")
    c.rect(500, 105, 398, 296, (0.040, 0.042, 0.058))
    c.text(530, 365, "Explore the Data", 24, COLORS["ink"], bold=True)
    c.rect(530, 320, 280, 32, COLORS["panel"], COLORS["line"], 1)
    c.text(548, 332, "Hamilton", 10.5, COLORS["ink"])
    c.rect(530, 245, 150, 58, COLORS["panel2"], COLORS["red"], 1)
    c.text(546, 282, "HAM", 9.5, COLORS["red"], mono=True, bold=True)
    c.text(546, 262, "Lewis Hamilton", 12, COLORS["ink"], bold=True)
    c.text(546, 246, "British  #44", 9.5, COLORS["muted"])
    c.rect(700, 245, 150, 58, COLORS["panel2"], COLORS["line"], 1)
    c.text(716, 282, "VER", 9.5, COLORS["red"], mono=True, bold=True)
    c.text(716, 262, "Max Verstappen", 12, COLORS["ink"], bold=True)
    c.text(716, 246, "Dutch  #33", 9.5, COLORS["muted"])
    c.rect(530, 160, 320, 54, COLORS["panel"], COLORS["line"], 1)
    c.text(548, 195, "Driver detail panel", 12, COLORS["ink"], bold=True)
    c.text(548, 174, "wins, podiums, points, races, seasons", 10, COLORS["muted"])
    c.paragraph(
        64,
        88,
        "The Django root page injects API_V1_PREFIX into the browser, so the static dashboard and the proxied API stay aligned under deployment-specific route prefixes.",
        826,
        11.6,
        COLORS["muted"],
    )


def add_api_demo_slide(deck: PDFDeck, number: int) -> None:
    c = Canvas(deck, "API Surface", "OpenAPI docs and typed analytics responses from the shared FastAPI core", number)
    c.browser_frame(62, 86, 398, 350, "http://127.0.0.1:8000/docs")
    c.rect(62, 86, 398, 316, COLORS["white"])
    c.text(86, 370, "F1 Analytics API", 19, (0.090, 0.110, 0.140), bold=True)
    c.text(86, 342, "Swagger UI - OpenAPI 3.1", 10.5, (0.350, 0.370, 0.410))
    for idx, (method, path, color) in enumerate(
        [
            ("GET", f"{settings.API_V1_PREFIX}/drivers", COLORS["green"]),
            ("POST", f"{settings.API_V1_PREFIX}/auth/login", COLORS["blue"]),
            ("GET", f"{settings.API_V1_PREFIX}/analytics/seasons/{{year}}/highlights", COLORS["green"]),
            ("GET", f"{settings.API_V1_PREFIX}/analytics/drivers/{{id}}/head-to-head/{{rival}}", COLORS["green"]),
        ]
    ):
        yy = 300 - idx * 48
        c.rect(86, yy, 330, 34, (0.930, 0.950, 0.970), (0.820, 0.850, 0.880), 0.8)
        c.rect(98, yy + 8, 46, 18, color)
        c.text(108, yy + 14, method, 7.5, COLORS["white"], bold=True)
        c.text(154, yy + 13, path, 8.5, (0.100, 0.130, 0.160), mono=True)

    c.browser_frame(500, 86, 398, 350, f"GET {settings.API_V1_PREFIX}/analytics/seasons/2023/highlights")
    c.rect(500, 86, 398, 316, (0.025, 0.028, 0.040))
    c.text(526, 370, "200 OK", 10.5, COLORS["green"], mono=True, bold=True)
    c.text(526, 342, "{", 10.5, COLORS["muted"], mono=True)
    json_lines = [
        '"season": 2023,',
        '"total_races": 22,',
        '"champion_driver": {',
        '  "name": "Max Verstappen",',
        '  "points": 575.0',
        "},",
        '"champion_constructor": {',
        '  "name": "Red Bull",',
        '  "points": 860.0',
        "},",
        '"unique_race_winners": 3',
    ]
    yy = 320
    for line in json_lines:
        c.text(542, yy, line, 8.9, COLORS["ink"] if ":" in line else COLORS["muted"], mono=True)
        yy -= 20
    c.text(526, yy, "}", 10.5, COLORS["muted"], mono=True)


def add_testing_slide(deck: PDFDeck, number: int) -> None:
    c = Canvas(deck, "Testing And Verification", "Repository-wide evidence for the current architecture", number)
    inventory = test_inventory()
    total = pytest_collected_count()
    c.stat(56, 330, 150, "Auth", str(inventory["auth"]), COLORS["cyan"], h=82, value_size=20.5, label_size=11.2)
    c.stat(224, 330, 150, "Analytics", str(inventory["analytics"]), COLORS["red"], h=82, value_size=20.5, label_size=11.2)
    c.stat(392, 330, 150, "Resource API", str(inventory["resource_api"]), COLORS["gold"], h=82, value_size=20.5, label_size=11.2)
    c.stat(560, 330, 150, "Infra+Import", str(inventory["infra_import"]), COLORS["green"], h=82, value_size=20.5, label_size=10.9)
    c.stat(728, 330, 104, "Platform", str(inventory["platform"]), COLORS["blue"], h=82, value_size=20.5, label_size=10.9)
    c.stat(848, 330, 64, "All", str(total), COLORS["purple"], h=82, value_size=17.0, label_size=10.0)

    c.rect(72, 150, 430, 140, COLORS["panel"], COLORS["line"], 1)
    c.text(94, 256, "Latest checks", 14, COLORS["ink"], bold=True)
    c.text(94, 228, "$ pytest -q", 10.4, COLORS["ink"], mono=True, bold=True)
    c.text(94, 208, f"{total} passed", 19.5, COLORS["green"], bold=True)
    c.text(94, 180, "$ python manage.py check", 10.4, COLORS["ink"], mono=True, bold=True)
    c.text(94, 162, "$ python scripts/django_openapi.py --file /tmp/f1_openapi.json", 9.3, COLORS["ink"], mono=True, bold=True)

    c.rect(542, 144, 350, 162, COLORS["panel"], COLORS["line"], 1)
    c.text(566, 274, "Acceptance coverage", 14, COLORS["ink"], bold=True)
    c.bullets(
        566,
        246,
        [
            "Django Client exercises the adapter path: root, docs, OpenAPI, static assets, and health.",
            "Register, form login, JSON login, refresh, auth/me, and protected writes all pass.",
            "Drivers, teams, circuits, races, results, and all six analytics endpoints are covered.",
            "A temporary SQLite copy is used so verification never mutates the main local database.",
        ],
        304,
        10.1,
    )

    c.paragraph(
        72,
        106,
        "Testing now demonstrates both dimensions of the submission: direct code quality through pytest and deployment behaviour through the Django acceptance suite.",
        812,
        12,
        COLORS["muted"],
    )


def add_deployment_slide(deck: PDFDeck, number: int) -> None:
    c = Canvas(deck, "Runtime Modes", "Direct ASGI development and Django WSGI deployment share the same API core", number)
    nodes = [
        (70, 315, 160, "Configure .env", "DATABASE_URL, SECRET_KEY, hosts, and API_V1_PREFIX"),
        (270, 315, 160, "Shared schema", "scripts/django_openapi.py exports the FastAPI schema used at runtime"),
        (470, 315, 160, "Direct ASGI", "uvicorn app.main:app --reload for local API development"),
        (670, 315, 170, "Django adapter", "manage.py migrate --fake-initial plus collectstatic for WSGI hosting"),
        (270, 165, 160, "WSGI entrypoint", "f1_django.wsgi for PythonAnywhere-style deployment"),
        (470, 165, 170, "Prefix-aware UI", "root_index injects API_V1_PREFIX into the static frontend"),
        (680, 165, 160, "Same behaviour", "Docs, auth, CRUD, analytics, and OpenAPI stay aligned"),
    ]
    for x, y, w, title, body in nodes:
        accent = COLORS["purple"] if "Django" in title or "WSGI" in title or "Same" in title else COLORS["red"]
        if "Direct ASGI" in title or "Shared schema" in title:
            accent = COLORS["gold"]
        if "Prefix-aware" in title:
            accent = COLORS["green"]
        c.card(x, y, w, 78, title, body, accent)
    c.arrow(230, 354, 270, 354, COLORS["red"], 2)
    c.arrow(430, 354, 470, 354, COLORS["gold"], 2)
    c.arrow(630, 354, 670, 354, COLORS["purple"], 2)
    c.arrow(350, 315, 350, 243, COLORS["purple"], 2)
    c.arrow(550, 315, 550, 243, COLORS["green"], 2)
    c.arrow(755, 315, 760, 243, COLORS["cyan"], 2)
    c.text(612, 120, "Development and deployment are different shells around the same FastAPI implementation", 10.0, COLORS["muted"])
    c.rect(72, 108, 362, 128, COLORS["panel"], COLORS["line"], 1)
    c.text(94, 210, "Operational notes", 13, COLORS["ink"], bold=True)
    c.bullets(
        94,
        186,
        [
            "Django deployment adopts existing tables with migrate --fake-initial rather than re-implementing schema logic.",
            "The shared importer and direct FastAPI path continue to use the same SQLAlchemy models and services.",
            "STATIC_ROOT and API_V1_PREFIX keep the browser experience aligned with the adapter route layout.",
        ],
        308,
        10.0,
    )


def add_close_slide(deck: PDFDeck, number: int) -> None:
    c = Canvas(deck, "Takeaways", "Why the regenerated deck matches the latest code more faithfully", number)
    c.card(72, 332, 250, 95, "One implementation", "FastAPI is the single API core for routes, validation, OpenAPI, auth, and analytics behaviour.", COLORS["cyan"])
    c.card(356, 332, 250, 95, "Cleaner codebase", "The Django layer is now a small adapter instead of a second parallel CRUD/auth stack.", COLORS["red"])
    c.card(640, 332, 250, 95, "Verified behaviour", "pytest, schema export, and Django acceptance checks all support the current architecture claims.", COLORS["gold"])
    c.card(72, 186, 250, 95, "Analytical depth", "Season, team, circuit, and driver endpoints go beyond baseline CRUD and show meaningful data modelling.", COLORS["green"])
    c.card(356, 186, 250, 95, "Deployment clarity", "Direct ASGI and Django WSGI modes are explained as two shells around the same core.", COLORS["purple"])
    c.card(640, 186, 250, 95, "Honest limits", "State is still in-memory and SQLite remains the verified database for this coursework build.", COLORS["blue"])
    c.paragraph(
        78,
        112,
        "Core message: this is not just a CRUD API. It is a refactored, documented, tested, and deployment-aware analytics service whose slides now match the code that actually runs.",
        790,
        15,
        COLORS["ink"],
    )


def build_deck() -> PDFDeck:
    operations, analytics = api_counts()
    total_tests = pytest_collected_count()
    deck = PDFDeck()
    add_title_slide(deck, 1, operations, analytics)
    add_scope_slide(deck, 2)
    add_refactor_slide(deck, 3, operations, total_tests)
    add_architecture_slide(deck, 4)
    add_database_slide(deck, 5)
    add_security_slide(deck, 6)
    add_frontend_demo_slide(deck, 7)
    add_api_demo_slide(deck, 8)
    add_testing_slide(deck, 9)
    add_deployment_slide(deck, 10)
    add_close_slide(deck, 11)
    return deck


def main() -> None:
    deck = build_deck()
    deck.build(OUTPUT_PATH)
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
