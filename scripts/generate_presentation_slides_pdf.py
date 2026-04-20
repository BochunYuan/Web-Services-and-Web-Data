#!/usr/bin/env python3
"""
Generate presentation slides for the F1 Analytics API coursework.

The deck is intentionally generated from code so it remains reproducible and
does not depend on PowerPoint, Keynote, or external PDF libraries. Diagrams and
demo panels are drawn directly into the PDF as vector slide elements.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = ROOT / "docs" / "presentation_slides.pdf"
sys.path.insert(0, str(ROOT))

from app.config import settings
from app.main import app
from scripts.generate_api_documentation_pdf import clean_text, escape_pdf_text, wrap_text

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

    def render_slide(self, slide: Slide) -> str:
        commands: list[str] = []
        for rect in slide.rects:
            commands.append(
                f"{rect.fill[0]:.3f} {rect.fill[1]:.3f} {rect.fill[2]:.3f} rg "
                f"{rect.x:.2f} {rect.y:.2f} {rect.w:.2f} {rect.h:.2f} re f"
            )
            if rect.stroke:
                commands.append(
                    f"{rect.stroke[0]:.3f} {rect.stroke[1]:.3f} {rect.stroke[2]:.3f} RG "
                    f"{rect.lw:.2f} w {rect.x:.2f} {rect.y:.2f} {rect.w:.2f} {rect.h:.2f} re S"
                )
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

    def card(self, x: float, y: float, w: float, h: float, title: str, body: str, accent: tuple[float, float, float] = COLORS["red"]) -> None:
        self.rect(x, y, w, h, COLORS["panel"], COLORS["line"], 1)
        self.rect(x, y + h - 5, w, 5, accent)
        self.text(x + 16, y + h - 28, title, 13, COLORS["ink"], bold=True)
        self.paragraph(x + 16, y + h - 50, body, w - 32, 10.2, COLORS["muted"], leading=14)

    def stat(self, x: float, y: float, w: float, label: str, value: str, color: tuple[float, float, float] = COLORS["red"]) -> None:
        self.rect(x, y, w, 70, COLORS["panel"], COLORS["line"], 1)
        self.text(x + 16, y + 40, value, 22, color, bold=True)
        self.text(x + 16, y + 18, label, 10, COLORS["muted"])

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


def api_counts() -> tuple[int, int]:
    schema = app.openapi()
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
    c.rect(x, y + h - 28, w, 28, color)
    c.text(x + 12, y + h - 20, name, 12, COLORS["white"], bold=True)
    fy = y + h - 44
    for field in fields[:7]:
        c.text(x + 12, fy, field, 8.4, COLORS["muted"], mono=True)
        fy -= 13


def add_title_slide(deck: PDFDeck, number: int, operations: int, analytics: int) -> None:
    c = Canvas(deck, "", number=number)
    c.text(72, 382, "F1 Analytics API", 42, COLORS["ink"], bold=True)
    c.text(72, 338, "Presentation Slides", 25, COLORS["red"], bold=True)
    c.paragraph(
        72,
        300,
        "A RESTful Formula 1 data platform with CRUD resources, six analytics endpoints, JWT security, automated tests, and an MCP server for AI tool access.",
        575,
        15,
        COLORS["muted"],
        leading=21,
    )
    c.stat(72, 170, 142, "Drivers", "861", COLORS["red"])
    c.stat(232, 170, 142, "Teams", "212", COLORS["gold"])
    c.stat(392, 170, 142, "Results", "26,759", COLORS["green"])
    c.stat(552, 170, 142, "OpenAPI ops", str(operations), COLORS["cyan"])
    c.stat(712, 170, 142, "Analytics", str(analytics), COLORS["purple"])
    c.rect(710, 276, 160, 128, COLORS["panel"], COLORS["line"], 1)
    c.text(732, 370, "Stack", 13, COLORS["ink"], bold=True)
    c.text(732, 342, "FastAPI", 11, COLORS["muted"])
    c.text(732, 320, "SQLAlchemy async", 11, COLORS["muted"])
    c.text(732, 298, "JWT + bcrypt", 11, COLORS["muted"])
    c.text(732, 276, "FastMCP", 11, COLORS["muted"])


def add_scope_slide(deck: PDFDeck, number: int) -> None:
    c = Canvas(deck, "Project Scope", "What the API delivers", number)
    c.card(64, 330, 250, 95, "CRUD resources", "Drivers, teams, circuits and races expose authenticated create, update and delete operations with pagination on list routes.", COLORS["red"])
    c.card(354, 330, 250, 95, "Read-only results", "Race results are imported from CSV and protected from API-side mutation because they are historical source data.", COLORS["gold"])
    c.card(644, 330, 250, 95, "Analytics layer", "Six endpoints aggregate points, wins, DNFs, circuit records, season highlights and head-to-head records.", COLORS["green"])
    c.card(64, 190, 250, 95, "Security", "JWT access and refresh tokens, bcrypt password hashing, explicit CORS origins and per-IP rate limiting.", COLORS["cyan"])
    c.card(354, 190, 250, 95, "Documentation", "Swagger UI, ReDoc, OpenAPI JSON, static API documentation PDF and this presentation deck.", COLORS["purple"])
    c.card(644, 190, 250, 95, "AI integration", "FastMCP wraps the HTTP API as AI-callable tools with driver and circuit discovery helpers.", COLORS["blue"])
    c.paragraph(
        70,
        116,
        "Design focus: a coursework-sized system that is still layered, testable, documented and demonstrably more analytical than a basic CRUD application.",
        810,
        13,
        COLORS["muted"],
    )


def add_architecture_slide(deck: PDFDeck, number: int) -> None:
    c = Canvas(deck, "Architecture Diagram", "Layered FastAPI service with analytics and MCP entry points", number)
    c.card(60, 345, 170, 70, "Frontend UI", "Static HTML/CSS/JS dashboard served from /static.", COLORS["red"])
    c.card(60, 245, 170, 70, "API docs", "Swagger UI, ReDoc and OpenAPI JSON.", COLORS["gold"])
    c.card(60, 145, 170, 70, "AI assistant", "Claude or MCP-compatible client.", COLORS["purple"])

    c.card(300, 360, 190, 82, "FastAPI app", "app/main.py registers middleware, routers, docs and static files.", COLORS["cyan"])
    c.card(300, 250, 190, 82, "Middleware", "CORS allow-list and sliding-window rate limiter.", COLORS["blue"])
    c.card(300, 140, 190, 82, "Routers", "auth, drivers, teams, circuits, races, results, analytics.", COLORS["green"])

    c.card(560, 360, 170, 82, "Services", "auth_service, analytics_service and cache_service.", COLORS["red"])
    c.card(560, 250, 170, 82, "Async DB session", "get_db yields one SQLAlchemy AsyncSession per request.", COLORS["gold"])
    c.card(560, 140, 170, 82, "FastMCP wrapper", "mcp_server/server.py calls the HTTP API.", COLORS["purple"])

    c.card(790, 305, 120, 72, "SQLite dev", "Local f1_analytics.db", COLORS["green"])
    c.card(790, 205, 120, 72, "MySQL prod", "URL switch via settings", COLORS["blue"])

    for y in [380, 280, 180]:
        c.arrow(230, y, 300, y, COLORS["red"], 2)
    c.arrow(490, 400, 560, 400, COLORS["cyan"], 2)
    c.arrow(490, 290, 560, 290, COLORS["cyan"], 2)
    c.arrow(490, 180, 560, 180, COLORS["cyan"], 2)
    c.arrow(730, 290, 790, 340, COLORS["gold"], 2)
    c.arrow(730, 290, 790, 240, COLORS["gold"], 2)
    c.arrow(645, 140, 645, 115, COLORS["purple"], 2)
    c.text(594, 98, "MCP tools preserve API validation and caching", 10, COLORS["muted"])


def add_database_slide(deck: PDFDeck, number: int) -> None:
    c = Canvas(deck, "Database Diagram", "Star-schema style analytics around the results fact table", number)
    table_box(c, 388, 215, 185, 175, "results", ["id PK", "race_id FK", "driver_id FK", "constructor_id FK", "position", "position_order", "points"], COLORS["red"])
    table_box(c, 82, 315, 180, 130, "drivers", ["id PK", "driver_ref UNIQUE", "forename", "surname INDEX", "nationality INDEX", "code"], COLORS["blue"])
    table_box(c, 82, 125, 180, 130, "teams", ["id PK", "constructor_ref UNIQUE", "name INDEX", "nationality", "url"], COLORS["purple"])
    table_box(c, 700, 315, 180, 130, "races", ["id PK", "year INDEX", "round", "circuit_id FK", "name", "date"], COLORS["green"])
    table_box(c, 700, 125, 180, 130, "circuits", ["id PK", "circuit_ref UNIQUE", "name", "location", "country INDEX", "lat / lng"], COLORS["gold"])
    table_box(c, 388, 70, 185, 105, "users", ["id PK", "username UNIQUE", "email UNIQUE", "hashed_password", "is_active"], COLORS["cyan"])

    c.arrow(262, 370, 388, 315, COLORS["blue"], 2)
    c.arrow(262, 190, 388, 260, COLORS["purple"], 2)
    c.arrow(700, 370, 573, 315, COLORS["green"], 2)
    c.arrow(790, 315, 790, 255, COLORS["gold"], 2)
    c.rect(296, 358, 100, 22, COLORS["bg"])
    c.text(306, 365, "1 driver -> many", 8.6, COLORS["muted"])
    c.rect(296, 178, 92, 22, COLORS["bg"])
    c.text(304, 185, "1 team -> many", 8.6, COLORS["muted"])
    c.rect(576, 358, 92, 22, COLORS["bg"])
    c.text(586, 365, "1 race -> many", 8.6, COLORS["muted"])
    c.rect(805, 284, 78, 24, COLORS["bg"])
    c.text(812, 292, "1 circuit", 8.4, COLORS["muted"])
    c.text(812, 280, "-> many races", 8.4, COLORS["muted"])
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
    c.card(70, 340, 190, 80, "Register/login", "Pydantic validates username, email and password before auth_service touches the database.", COLORS["red"])
    c.card(305, 340, 190, 80, "bcrypt hash", "User passwords are stored as bcrypt hashes, never plain text or response fields.", COLORS["gold"])
    c.card(540, 340, 190, 80, "Token pair", "Access token: 30 minutes. Refresh token: 7 days.", COLORS["green"])
    c.card(305, 205, 190, 80, "Protected writes", "POST, PUT and DELETE depend on get_current_active_user.", COLORS["cyan"])
    c.card(540, 205, 190, 80, "Rate limit", "Sliding-window per-IP limiter returns 429 and Retry-After.", COLORS["purple"])
    c.card(70, 205, 190, 80, "CORS", "Explicit allowed origins, not wildcard browser access.", COLORS["blue"])
    c.arrow(260, 380, 305, 380, COLORS["red"], 2)
    c.arrow(495, 380, 540, 380, COLORS["red"], 2)
    c.arrow(635, 340, 635, 285, COLORS["green"], 2)
    c.arrow(540, 245, 495, 245, COLORS["cyan"], 2)
    c.arrow(305, 245, 260, 245, COLORS["cyan"], 2)
    c.rect(770, 190, 120, 230, COLORS["panel"], COLORS["line"], 1)
    c.text(792, 390, "Status codes", 13, COLORS["ink"], bold=True)
    c.text(792, 356, "401 invalid token", 10, COLORS["muted"], mono=True)
    c.text(792, 332, "403 inactive user", 10, COLORS["muted"], mono=True)
    c.text(792, 308, "409 conflict", 10, COLORS["muted"], mono=True)
    c.text(792, 284, "422 validation", 10, COLORS["muted"], mono=True)
    c.text(792, 260, "429 rate limit", 10, COLORS["muted"], mono=True)
    c.paragraph(72, 126, "Important detail: login uses a dummy bcrypt hash when a username does not exist, reducing user-enumeration risk from timing differences.", 790, 12, COLORS["muted"])


def add_frontend_demo_slide(deck: PDFDeck, number: int) -> None:
    c = Canvas(deck, "Demo Screenshots", "Frontend dashboard and driver exploration flow", number)
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


def add_api_demo_slide(deck: PDFDeck, number: int) -> None:
    c = Canvas(deck, "Demo Screenshots", "API documentation and analytics response examples", number)
    c.browser_frame(62, 86, 398, 350, "http://127.0.0.1:8000/docs")
    c.rect(62, 86, 398, 316, COLORS["white"])
    c.text(86, 370, "F1 Analytics API", 19, (0.090, 0.110, 0.140), bold=True)
    c.text(86, 342, "Swagger UI - OpenAPI 3.1", 10.5, (0.350, 0.370, 0.410))
    for idx, (method, path, color) in enumerate(
        [
            ("GET", "/api/v1/drivers", COLORS["green"]),
            ("POST", "/api/v1/auth/login", COLORS["blue"]),
            ("GET", "/api/v1/analytics/seasons/{year}/highlights", COLORS["green"]),
            ("GET", "/api/v1/analytics/drivers/{id}/head-to-head/{rival}", COLORS["green"]),
        ]
    ):
        yy = 300 - idx * 48
        c.rect(86, yy, 330, 34, (0.930, 0.950, 0.970), (0.820, 0.850, 0.880), 0.8)
        c.rect(98, yy + 8, 46, 18, color)
        c.text(108, yy + 14, method, 7.5, COLORS["white"], bold=True)
        c.text(154, yy + 13, path, 8.5, (0.100, 0.130, 0.160), mono=True)

    c.browser_frame(500, 86, 398, 350, "GET /api/v1/analytics/seasons/2023/highlights")
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
    c = Canvas(deck, "Test Result", "Automated verification using pytest, pytest-asyncio and httpx", number)
    auth = count_tests("tests/test_auth.py")
    drivers = count_tests("tests/test_drivers.py")
    analytics = count_tests("tests/test_analytics.py")
    results = count_tests("tests/test_results.py")
    total = auth + drivers + analytics + results
    c.stat(72, 338, 150, "Auth tests", str(auth), COLORS["cyan"])
    c.stat(246, 338, 150, "Driver tests", str(drivers), COLORS["red"])
    c.stat(420, 338, 150, "Analytics tests", str(analytics), COLORS["gold"])
    c.stat(594, 338, 150, "Result tests", str(results), COLORS["green"])
    c.stat(768, 338, 120, "Total", str(total), COLORS["purple"])
    c.rect(72, 156, 420, 132, COLORS["panel"], COLORS["line"], 1)
    c.text(96, 254, "$ ./venv/bin/pytest", 13, COLORS["ink"], mono=True, bold=True)
    c.text(96, 224, "67 passed, 2 warnings", 25, COLORS["green"], bold=True)
    c.text(96, 194, "Latest local verification in this workspace", 11, COLORS["muted"])
    c.rect(542, 144, 346, 162, COLORS["panel"], COLORS["line"], 1)
    c.text(566, 274, "What is covered", 14, COLORS["ink"], bold=True)
    c.bullets(
        566,
        246,
        [
            "JWT auth lifecycle: register, login, refresh and protected route access.",
            "Driver CRUD validation, pagination, conflicts and auth requirements.",
            "All six analytics endpoints with deterministic seed data.",
            "Result filtering by race, driver and finish status.",
        ],
        300,
        10.5,
    )
    c.paragraph(
        72,
        104,
        "Testing uses a separate SQLite database, FastAPI dependency overrides and ASGITransport, so requests exercise the real app without touching production data.",
        780,
        12,
        COLORS["muted"],
    )


def add_mcp_slide(deck: PDFDeck, number: int) -> None:
    c = Canvas(deck, "MCP Workflow", "AI assistant access to the same analytics API", number)
    nodes = [
        (70, 315, 150, "User question", "Compare Hamilton and Rosberg"),
        (270, 315, 150, "Claude Desktop", "Chooses MCP tools"),
        (470, 315, 150, "search_drivers", "Find numeric IDs"),
        (670, 315, 170, "get_head_to_head", "Call analytics endpoint"),
        (470, 165, 150, "FastAPI HTTP", "/api/v1/..."),
        (670, 165, 170, "JSON answer", "Shared races + win %"),
    ]
    for x, y, w, title, body in nodes:
        c.card(x, y, w, 78, title, body, COLORS["purple"] if "Claude" in title or "search" in title or "head" in title else COLORS["red"])
    c.arrow(220, 354, 270, 354, COLORS["red"], 2)
    c.arrow(420, 354, 470, 354, COLORS["red"], 2)
    c.arrow(620, 354, 670, 354, COLORS["red"], 2)
    c.arrow(755, 315, 545, 243, COLORS["gold"], 2)
    c.arrow(620, 204, 670, 204, COLORS["gold"], 2)
    c.arrow(755, 165, 755, 140, COLORS["green"], 2)
    c.text(692, 120, "AI response with sourced, structured stats", 10.5, COLORS["muted"])
    c.rect(72, 118, 320, 126, COLORS["panel"], COLORS["line"], 1)
    c.text(94, 218, "MCP tools in server.py", 13, COLORS["ink"], bold=True)
    c.bullets(
        94,
        194,
        [
            "Discovery: search_drivers, search_circuits",
            "Analytics: performance, compare, standings, highlights, circuit stats, head-to-head",
            "Thin wrapper: HTTP calls preserve validation and caching",
        ],
        270,
        10.2,
    )


def add_close_slide(deck: PDFDeck, number: int) -> None:
    c = Canvas(deck, "Takeaways", "Why this submission is technically strong", number)
    c.card(72, 332, 250, 95, "Layered architecture", "Routers, services, models, schemas and core utilities are separated cleanly.", COLORS["cyan"])
    c.card(356, 332, 250, 95, "Analytics depth", "Conditional aggregation, subqueries and self-joins create meaningful F1 insights.", COLORS["red"])
    c.card(640, 332, 250, 95, "Submission readiness", "Static PDFs, runtime docs, tests and slides are committed deliverables.", COLORS["gold"])
    c.card(72, 186, 250, 95, "Security baseline", "JWT, bcrypt, rate limiting, CORS and typed settings are implemented.", COLORS["green"])
    c.card(356, 186, 250, 95, "MCP novelty", "AI assistants can query analytics tools directly instead of scraping pages.", COLORS["purple"])
    c.card(640, 186, 250, 95, "Honest limitations", "Future work is clear: CI automation, Redis state sharing and token revocation.", COLORS["blue"])
    c.paragraph(
        78,
        112,
        "Core message: this is not just a CRUD API. It is a documented, tested and AI-accessible analytics service built around a coherent data model.",
        790,
        15,
        COLORS["ink"],
    )


def build_deck() -> PDFDeck:
    operations, analytics = api_counts()
    deck = PDFDeck()
    add_title_slide(deck, 1, operations, analytics)
    add_scope_slide(deck, 2)
    add_architecture_slide(deck, 3)
    add_database_slide(deck, 4)
    add_security_slide(deck, 5)
    add_frontend_demo_slide(deck, 6)
    add_api_demo_slide(deck, 7)
    add_testing_slide(deck, 8)
    add_mcp_slide(deck, 9)
    add_close_slide(deck, 10)
    return deck


def main() -> None:
    deck = build_deck()
    deck.build(OUTPUT_PATH)
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
