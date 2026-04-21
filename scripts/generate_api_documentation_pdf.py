#!/usr/bin/env python3
"""
Generate a static PDF export of the API documentation.

This script intentionally uses only the Python standard library so it can run
inside the coursework environment without extra PDF dependencies.

The generated document is based on the FastAPI OpenAPI schema exposed through
the Django deployment adapter plus a small amount of curated project-specific commentary for analytics
responses, security, and deployment notes that benefit from prose.
"""

from __future__ import annotations

import json
import math
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = ROOT / "docs" / "api_documentation.pdf"
sys.path.insert(0, str(ROOT))

from scripts.django_openapi import get_django_settings, get_openapi_schema

settings = get_django_settings()

A4_WIDTH = 595.28
A4_HEIGHT = 841.89
LEFT_MARGIN = 54
RIGHT_MARGIN = 54
TOP_MARGIN = 72
BOTTOM_MARGIN = 56
CONTENT_WIDTH = A4_WIDTH - LEFT_MARGIN - RIGHT_MARGIN

COLORS = {
    "ink": (0.11, 0.16, 0.24),
    "muted": (0.37, 0.42, 0.50),
    "soft": (0.57, 0.62, 0.70),
    "rule": (0.86, 0.89, 0.93),
    "panel": (0.96, 0.97, 0.99),
    "panel_alt": (0.94, 0.95, 0.98),
    "brand": (0.10, 0.27, 0.51),
    "brand_soft": (0.87, 0.92, 0.98),
    "success": (0.15, 0.45, 0.28),
    "warning": (0.74, 0.47, 0.10),
    "danger": (0.70, 0.16, 0.16),
    "purple": (0.35, 0.24, 0.59),
}

FONT_MAP = {
    "body": "F1",
    "body_bold": "F2",
    "mono": "F3",
    "mono_bold": "F4",
}

METHOD_COLORS = {
    "GET": (0.14, 0.46, 0.28),
    "POST": (0.08, 0.33, 0.70),
    "PUT": (0.68, 0.45, 0.10),
    "DELETE": (0.72, 0.18, 0.18),
}

GROUP_INTROS = {
    "Authentication": (
        "Authentication is implemented with JWT bearer tokens. The API issues a "
        "short-lived access token and a long-lived refresh token, supports both "
        "form login and JSON login, and protects write operations with the "
        "current active user permission."
    ),
    "Drivers": (
        "Driver endpoints provide full CRUD plus pagination and filtering by "
        "nationality and surname search. Write actions require authentication."
    ),
    "Teams": (
        "Team endpoints expose constructor data as a standard CRUD resource with "
        "pagination and optional nationality/name filtering."
    ),
    "Circuits": (
        "Circuit endpoints manage track metadata, including optional location "
        "and geographic coordinates useful for analytics and visualisation."
    ),
    "Races": (
        "Race endpoints expose the season calendar and embed nested circuit "
        "summaries in responses. The write path enforces uniqueness of "
        "(year, round) to avoid duplicate calendar rounds."
    ),
    "Results": (
        "Results are intentionally read-only because they are imported from the "
        "Ergast dataset. These endpoints support filtering and pagination and "
        "serve as the foundation for the analytics layer."
    ),
    "Analytics": (
        "Analytics endpoints are read-only, uncached at the HTTP contract level "
        "but cached internally in the service layer. They aggregate historical "
        "race data into reusable insights for dashboards, reports, and API consumers."
    ),
}

ANALYTICS_DETAILS = {
    ("GET", f"{settings.API_V1_PREFIX}/analytics/drivers/{{driver_id}}/performance"): {
        "response_fields": [
            "driver: id, name, nationality, code",
            "seasons[]: year, total_points, wins, podiums, races_entered, dnfs, win_rate",
            "career_summary: total_seasons, total_points, total_wins, total_podiums, total_races",
        ],
        "notes": [
            "DNFs are counted when position is null and status is not Finished.",
            "Results are cached for 10 minutes.",
        ],
        "example": {
            "driver": {"id": 1, "name": "Lewis Hamilton", "nationality": "British", "code": "HAM"},
            "seasons": [
                {
                    "year": 2014,
                    "total_points": 384.5,
                    "wins": 11,
                    "podiums": 16,
                    "races_entered": 19,
                    "dnfs": 2,
                    "win_rate": 57.9,
                }
            ],
            "career_summary": {
                "total_seasons": 17,
                "total_points": 4639.5,
                "total_wins": 103,
                "total_podiums": 197,
                "total_races": 333,
            },
        },
    },
    ("GET", f"{settings.API_V1_PREFIX}/analytics/drivers/compare"): {
        "response_fields": [
            "drivers_compared: integer",
            "comparisons[]: driver object plus stats",
            "stats: total_points, wins, podiums, races_entered, dnfs, seasons, win_rate_pct, points_per_race",
        ],
        "notes": [
            "Accepts between 2 and 5 driver_ids.",
            "Order in the response matches the order in the request.",
        ],
        "example": {
            "drivers_compared": 2,
            "comparisons": [
                {
                    "driver": {"id": 1, "name": "Lewis Hamilton", "nationality": "British", "code": "HAM"},
                    "stats": {
                        "total_points": 4639.5,
                        "wins": 103,
                        "podiums": 197,
                        "races_entered": 333,
                        "dnfs": 29,
                        "seasons": 17,
                        "win_rate_pct": 30.9,
                        "points_per_race": 13.93,
                    },
                }
            ],
        },
    },
    ("GET", f"{settings.API_V1_PREFIX}/analytics/teams/standings/{{year}}"): {
        "response_fields": [
            "season: integer",
            "total_races: integer",
            "standings[]: position, team_id, team_name, nationality, total_points, wins, race_entries, drivers_used",
        ],
        "notes": [
            "Standings are ordered by total constructor points descending.",
            "Results are cached for 10 minutes.",
        ],
        "example": {
            "season": 2023,
            "total_races": 22,
            "standings": [
                {"position": 1, "team_name": "Red Bull", "total_points": 860.0, "wins": 21},
                {"position": 2, "team_name": "Mercedes", "total_points": 409.0, "wins": 1},
            ],
        },
    },
    ("GET", f"{settings.API_V1_PREFIX}/analytics/seasons/{{year}}/highlights"): {
        "response_fields": [
            "season: integer",
            "total_races: integer",
            "champion_driver: id, name, points",
            "champion_constructor: id, name, points",
            "most_race_wins: driver, wins",
            "unique_race_winners: integer",
            "total_points_scored: float",
        ],
        "notes": [
            "Uses aggregate queries and winner subqueries to identify champions.",
            "Results are cached for 30 minutes.",
        ],
        "example": {
            "season": 2021,
            "total_races": 22,
            "champion_driver": {"id": 830, "name": "Max Verstappen", "points": 395.5},
            "champion_constructor": {"id": 9, "name": "Red Bull", "points": 585.5},
            "most_race_wins": {"driver": "Max Verstappen", "wins": 10},
            "unique_race_winners": 3,
            "total_points_scored": 2446.5,
        },
    },
    ("GET", f"{settings.API_V1_PREFIX}/analytics/circuits/{{circuit_id}}/stats"): {
        "response_fields": [
            "circuit: id, name, location, country, lat, lng",
            "total_races_hosted: integer",
            "first_race_year / last_race_year: integer",
            "top_winners[]: driver, wins",
            "most_successful_constructor: name, wins, total_points",
        ],
        "notes": [
            "Returns a no-data message when the circuit exists but has no race history.",
            "Results are cached for 10 minutes.",
        ],
        "example": {
            "circuit": {"id": 6, "name": "Circuit de Monaco", "country": "Monaco"},
            "total_races_hosted": 69,
            "first_race_year": 1950,
            "last_race_year": 2024,
            "top_winners": [{"driver": "Ayrton Senna", "wins": 6}],
            "most_successful_constructor": {"name": "McLaren", "wins": 15, "total_points": 468.5},
        },
    },
    ("GET", f"{settings.API_V1_PREFIX}/analytics/drivers/{{driver_id}}/head-to-head/{{rival_id}}"): {
        "response_fields": [
            "driver / rival: id, name",
            "shared_races: integer",
            "head_to_head: driver_wins, rival_wins, ties, driver_win_pct, rival_win_pct",
            "points_in_shared_races: driver_points, rival_points",
        ],
        "notes": [
            "Uses position_order rather than position so DNFs are handled correctly.",
            "Returns a no-shared-races message when the drivers never raced together.",
        ],
        "example": {
            "driver": {"id": 1, "name": "Lewis Hamilton"},
            "rival": {"id": 3, "name": "Nico Rosberg"},
            "shared_races": 161,
            "head_to_head": {
                "driver_wins": 97,
                "rival_wins": 64,
                "ties": 0,
                "driver_win_pct": 60.2,
                "rival_win_pct": 39.8,
            },
            "points_in_shared_races": {"driver_points": 1943.5, "rival_points": 1581.0},
        },
    },
}

STATUS_NOTES = [
    ("200 OK", "Successful read, update, login, refresh, or analytics response."),
    ("201 Created", "Successful creation of a new resource such as a user or driver."),
    ("204 No Content", "Successful delete operation with an empty response body."),
    ("401 Unauthorized", "Missing token, invalid token, bad credentials, or invalid refresh token."),
    ("403 Forbidden", "Authenticated user exists but the account is disabled."),
    ("404 Not Found", "Requested resource or season/circuit/driver does not exist."),
    ("409 Conflict", "Uniqueness conflict such as duplicate username, driver_ref, or season round."),
    ("422 Unprocessable Entity", "Validation failure for query parameters or request body."),
    ("429 Too Many Requests", "Rate limit exceeded; response includes Retry-After and rate-limit headers."),
]


def clean_text(value: str) -> str:
    replacements = {
        "\u2013": "-",
        "\u2014": "-",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2026": "...",
        "\u2192": "->",
        "\u00d7": "x",
        "\u2264": "<=",
        "\u2265": ">=",
        "\u2212": "-",
        "\u2022": "-",
        "\u00a0": " ",
    }
    for old, new in replacements.items():
        value = value.replace(old, new)
    value = value.replace("\r", "")
    value = re.sub(r"\*\*(.*?)\*\*", r"\1", value)
    value = value.replace("`", "")
    return value.encode("latin-1", "ignore").decode("latin-1").strip()


def human_type(schema: dict[str, Any]) -> str:
    if "$ref" in schema:
        return schema["$ref"].split("/")[-1]
    if "anyOf" in schema:
        parts = [human_type(item) for item in schema["anyOf"] if item.get("type") != "null"]
        nullable = any(item.get("type") == "null" for item in schema["anyOf"])
        if not parts:
            parts = ["object"]
        label = " | ".join(parts)
        return f"{label} | null" if nullable else label
    if schema.get("type") == "array":
        return f"array[{human_type(schema.get('items', {}))}]"
    if schema.get("type"):
        label = schema["type"]
        if schema.get("format"):
            label += f" ({schema['format']})"
        return label
    if schema.get("properties"):
        return "object"
    return "object"


def pretty_json(data: Any) -> str:
    return json.dumps(data, indent=2, ensure_ascii=True)


def escape_pdf_text(text: str) -> str:
    text = text.replace("\\", "\\\\")
    text = text.replace("(", "\\(")
    text = text.replace(")", "\\)")
    return text


def estimate_char_width(ch: str, mono: bool = False) -> float:
    if mono:
        return 0.60
    if ch == " ":
        return 0.28
    if ch in "il.,:;!'|`":
        return 0.25
    if ch in "MW@#%&":
        return 0.88
    if ch.isupper():
        return 0.66
    if ch.isdigit():
        return 0.55
    return 0.52


def estimate_text_width(text: str, font_size: float, mono: bool = False) -> float:
    return sum(estimate_char_width(ch, mono=mono) for ch in text) * font_size


def wrap_text(text: str, width: float, font_size: float, mono: bool = False) -> list[str]:
    text = clean_text(text)
    if not text:
        return [""]

    lines: list[str] = []
    for paragraph in text.split("\n"):
        paragraph = paragraph.rstrip()
        if not paragraph:
            lines.append("")
            continue

        words = paragraph.split(" ")
        current = ""
        for word in words:
            candidate = word if not current else f"{current} {word}"
            if estimate_text_width(candidate, font_size, mono=mono) <= width:
                current = candidate
                continue

            if current:
                lines.append(current)
                current = word
                continue

            fragment = ""
            for ch in word:
                candidate = fragment + ch
                if estimate_text_width(candidate, font_size, mono=mono) <= width:
                    fragment = candidate
                else:
                    lines.append(fragment)
                    fragment = ch
            current = fragment
        if current:
            lines.append(current)
    return lines or [""]


@dataclass
class TextRun:
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
    width: float
    height: float
    fill: tuple[float, float, float]
    stroke: tuple[float, float, float] | None = None
    line_width: float = 1


@dataclass
class Line:
    x1: float
    y1: float
    x2: float
    y2: float
    color: tuple[float, float, float]
    line_width: float = 1


@dataclass
class Page:
    texts: list[TextRun] = field(default_factory=list)
    rects: list[Rect] = field(default_factory=list)
    lines: list[Line] = field(default_factory=list)


class PDFBuilder:
    def __init__(self) -> None:
        self.pages: list[Page] = []

    def build(self, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)

        objects: list[bytes] = []

        def add_object(payload: bytes) -> int:
            objects.append(payload)
            return len(objects)

        font_regular = add_object(
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"
        )
        font_bold = add_object(
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>"
        )
        font_mono = add_object(
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier /Encoding /WinAnsiEncoding >>"
        )
        font_mono_bold = add_object(
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier-Bold /Encoding /WinAnsiEncoding >>"
        )

        page_object_ids: list[int] = []
        pending_pages: list[dict[str, int]] = []

        for page in self.pages:
            stream = self.render_page(page).encode("latin-1", errors="replace")
            content_id = add_object(
                f"<< /Length {len(stream)} >>\nstream\n".encode("latin-1") + stream + b"\nendstream"
            )
            page_id = add_object(b"<< >>")
            page_object_ids.append(page_id)
            pending_pages.append({"page_id": page_id, "content_id": content_id})

        kids = " ".join(f"{page_id} 0 R" for page_id in page_object_ids)
        pages_id = add_object(
            f"<< /Type /Pages /Kids [{kids}] /Count {len(page_object_ids)} >>".encode("latin-1")
        )

        for entry in pending_pages:
            page_payload = (
                f"<< /Type /Page /Parent {pages_id} 0 R "
                f"/MediaBox [0 0 {A4_WIDTH:.2f} {A4_HEIGHT:.2f}] "
                f"/Resources << /Font << /F1 {font_regular} 0 R /F2 {font_bold} 0 R "
                f"/F3 {font_mono} 0 R /F4 {font_mono_bold} 0 R >> >> "
                f"/Contents {entry['content_id']} 0 R >>"
            ).encode("latin-1")
            objects[entry["page_id"] - 1] = page_payload

        catalog_id = add_object(f"<< /Type /Catalog /Pages {pages_id} 0 R >>".encode("latin-1"))

        buffer = bytearray()
        buffer.extend(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offsets = [0]

        for object_id, payload in enumerate(objects, start=1):
            offsets.append(len(buffer))
            buffer.extend(f"{object_id} 0 obj\n".encode("latin-1"))
            buffer.extend(payload)
            buffer.extend(b"\nendobj\n")

        xref_offset = len(buffer)
        buffer.extend(f"xref\n0 {len(objects) + 1}\n".encode("latin-1"))
        buffer.extend(b"0000000000 65535 f \n")
        for offset in offsets[1:]:
            buffer.extend(f"{offset:010d} 00000 n \n".encode("latin-1"))

        trailer = (
            f"trailer\n<< /Size {len(objects) + 1} /Root {catalog_id} 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        )
        buffer.extend(trailer.encode("latin-1"))
        output_path.write_bytes(buffer)

    def render_page(self, page: Page) -> str:
        commands: list[str] = []
        for rect in page.rects:
            commands.append(
                f"{rect.fill[0]:.3f} {rect.fill[1]:.3f} {rect.fill[2]:.3f} rg "
                f"{rect.x:.2f} {rect.y:.2f} {rect.width:.2f} {rect.height:.2f} re f"
            )
            if rect.stroke is not None:
                commands.append(
                    f"{rect.stroke[0]:.3f} {rect.stroke[1]:.3f} {rect.stroke[2]:.3f} RG "
                    f"{rect.line_width:.2f} w {rect.x:.2f} {rect.y:.2f} {rect.width:.2f} {rect.height:.2f} re S"
                )
        for line in page.lines:
            commands.append(
                f"{line.color[0]:.3f} {line.color[1]:.3f} {line.color[2]:.3f} RG "
                f"{line.line_width:.2f} w {line.x1:.2f} {line.y1:.2f} m {line.x2:.2f} {line.y2:.2f} l S"
            )
        for text in page.texts:
            commands.append(
                "BT "
                f"/{text.font} {text.size:.2f} Tf "
                f"{text.color[0]:.3f} {text.color[1]:.3f} {text.color[2]:.3f} rg "
                f"1 0 0 1 {text.x:.2f} {text.y:.2f} Tm "
                f"({escape_pdf_text(text.text)}) Tj ET"
            )
        return "\n".join(commands)


class Layout:
    def __init__(self, doc: PDFBuilder) -> None:
        self.doc = doc
        self.generated_on = datetime.now().strftime("%Y-%m-%d %H:%M")
        self.page_number = 0
        self.page: Page | None = None
        self.cursor_y = 0.0
        self.section_pages: dict[str, int] = {}
        self._new_page()

    def _new_page(self) -> None:
        self.page = Page()
        self.doc.pages.append(self.page)
        self.page_number += 1
        self.cursor_y = A4_HEIGHT - TOP_MARGIN
        self._draw_header_footer()

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
                A4_WIDTH - RIGHT_MARGIN - 145,
                A4_HEIGHT - 34,
                "Static API Documentation",
                FONT_MAP["body"],
                10,
                COLORS["muted"],
            )
        )
        self.page.texts.append(
            TextRun(LEFT_MARGIN, 22, f"Generated from code on {self.generated_on}", FONT_MAP["body"], 9, COLORS["muted"])
        )
        self.page.texts.append(
            TextRun(A4_WIDTH - RIGHT_MARGIN - 52, 22, f"Page {self.page_number}", FONT_MAP["body"], 9, COLORS["muted"])
        )

    def ensure_space(self, needed: float) -> None:
        if self.cursor_y - needed < BOTTOM_MARGIN:
            self._new_page()

    def add_text_line(
        self,
        text: str,
        x: float,
        y: float,
        font: str,
        size: float,
        color: tuple[float, float, float],
    ) -> None:
        assert self.page is not None
        self.page.texts.append(TextRun(x, y, text, font, size, color))

    def add_title_page(self, stats: list[tuple[str, str]]) -> None:
        assert self.page is not None
        top_box_y = A4_HEIGHT - 308
        top_box_height = 220
        self.page.rects.append(Rect(LEFT_MARGIN, top_box_y, CONTENT_WIDTH, top_box_height, COLORS["brand_soft"]))
        self.page.texts.append(
            TextRun(LEFT_MARGIN + 30, top_box_y + 166, "F1 Analytics API", FONT_MAP["body_bold"], 28, COLORS["brand"])
        )
        self.page.texts.append(
            TextRun(
                LEFT_MARGIN + 30,
                top_box_y + 134,
                "Static API Documentation",
                FONT_MAP["body_bold"],
                18,
                COLORS["ink"],
            )
        )
        self.page.texts.append(
            TextRun(
                LEFT_MARGIN + 30,
                top_box_y + 92,
                "FastAPI Core + Django Adapter + JWT + Analytics",
                FONT_MAP["body"],
                13,
                COLORS["muted"],
            )
        )

        overview = (
            "This document is a committed PDF export of the F1 Analytics API. "
            "It is generated from the live Django OpenAPI schema and augmented "
            "with project-specific notes for analytics responses, authentication, "
            "security behaviour, and Django deployment notes."
        )
        lines = wrap_text(overview, CONTENT_WIDTH - 60, 11.5)
        y = top_box_y + 54
        for line in lines:
            self.page.texts.append(TextRun(LEFT_MARGIN + 30, y, line, FONT_MAP["body"], 11.5, COLORS["ink"]))
            y -= 15

        stat_y = top_box_y - 82
        col_x = LEFT_MARGIN
        box_width = (CONTENT_WIDTH - 16) / 2
        box_height = 54
        for idx, (label, value) in enumerate(stats):
            x = col_x + (idx % 2) * (box_width + 16)
            if idx and idx % 2 == 0:
                stat_y -= box_height + 14
            self.page.rects.append(Rect(x, stat_y, box_width, box_height, COLORS["panel"]))
            self.page.texts.append(TextRun(x + 16, stat_y + 31, label, FONT_MAP["body"], 10.5, COLORS["muted"]))
            self.page.texts.append(TextRun(x + 16, stat_y + 12, value, FONT_MAP["body_bold"], 15, COLORS["ink"]))

        self.page.texts.append(
            TextRun(
                LEFT_MARGIN,
                92,
                f"Project version: {settings.PROJECT_VERSION}    Base prefix: {settings.API_V1_PREFIX}",
                FONT_MAP["body"],
                10,
                COLORS["muted"],
            )
        )
        self.page.texts.append(
            TextRun(
                LEFT_MARGIN,
                72,
                "Primary runtime docs: /docs, /redoc, /openapi.json    Static export: docs/api_documentation.pdf",
                FONT_MAP["body"],
                10,
                COLORS["muted"],
            )
        )
        self._new_page()

    def add_section_heading(self, title: str, intro: str | None = None) -> None:
        pre_gap = 14 if self.cursor_y < A4_HEIGHT - TOP_MARGIN - 1 else 0
        self.ensure_space(86 + pre_gap)
        if pre_gap:
            self.cursor_y -= pre_gap
        self.section_pages.setdefault(title, self.page_number)
        self.cursor_y -= 6
        self.add_text_line(title, LEFT_MARGIN, self.cursor_y, FONT_MAP["body_bold"], 20, COLORS["brand"])
        self.cursor_y -= 10
        assert self.page is not None
        self.page.lines.append(
            Line(LEFT_MARGIN, self.cursor_y, LEFT_MARGIN + 120, self.cursor_y, COLORS["brand"], 2)
        )
        self.cursor_y -= 22
        if intro:
            self.add_paragraph(intro, size=11.5, color=COLORS["ink"])
            self.cursor_y -= 8

    def add_subheading(self, title: str) -> None:
        pre_gap = 10 if self.cursor_y < A4_HEIGHT - TOP_MARGIN - 1 else 0
        self.ensure_space(42 + pre_gap)
        if pre_gap:
            self.cursor_y -= pre_gap
        self.add_text_line(title, LEFT_MARGIN, self.cursor_y, FONT_MAP["body_bold"], 14, COLORS["ink"])
        self.cursor_y -= 24

    def add_paragraph(
        self,
        text: str,
        *,
        size: float = 10.8,
        color: tuple[float, float, float] = COLORS["ink"],
        width: float = CONTENT_WIDTH,
        x: float = LEFT_MARGIN,
        leading: float | None = None,
    ) -> None:
        leading = leading or (size + 4.4)
        lines = wrap_text(text, width, size)
        height = len(lines) * leading
        self.ensure_space(height + 4)
        for line in lines:
            self.add_text_line(line, x, self.cursor_y, FONT_MAP["body"], size, color)
            self.cursor_y -= leading
        self.cursor_y -= 2

    def add_bullets(self, items: Iterable[str], *, size: float = 10.5, indent: float = 14) -> None:
        for item in items:
            wrapped = wrap_text(item, CONTENT_WIDTH - indent - 10, size)
            needed = len(wrapped) * (size + 4.2) + 2
            self.ensure_space(needed)
            self.add_text_line("-", LEFT_MARGIN, self.cursor_y, FONT_MAP["body_bold"], size + 1, COLORS["brand"])
            first_x = LEFT_MARGIN + indent
            self.add_text_line(wrapped[0], first_x, self.cursor_y, FONT_MAP["body"], size, COLORS["ink"])
            self.cursor_y -= size + 4.2
            for line in wrapped[1:]:
                self.add_text_line(line, first_x, self.cursor_y, FONT_MAP["body"], size, COLORS["ink"])
                self.cursor_y -= size + 4.2
            self.cursor_y -= 2

    def add_key_value_list(self, rows: list[tuple[str, str]]) -> None:
        label_width = 108
        for label, value in rows:
            wrapped = wrap_text(value, CONTENT_WIDTH - label_width - 10, 10.4)
            needed = len(wrapped) * 14 + 2
            self.ensure_space(needed + 4)
            self.add_text_line(label, LEFT_MARGIN, self.cursor_y, FONT_MAP["body_bold"], 10.4, COLORS["ink"])
            self.add_text_line(wrapped[0], LEFT_MARGIN + label_width, self.cursor_y, FONT_MAP["body"], 10.4, COLORS["ink"])
            self.cursor_y -= 14
            for line in wrapped[1:]:
                self.add_text_line(line, LEFT_MARGIN + label_width, self.cursor_y, FONT_MAP["body"], 10.4, COLORS["ink"])
                self.cursor_y -= 14
            self.cursor_y -= 2

    def add_code_block(self, code: str, *, label: str | None = None) -> None:
        code = code.strip("\n")
        raw_lines = code.splitlines() or [""]
        wrapped_lines: list[str] = []
        for raw in raw_lines:
            wrapped_lines.extend(wrap_text(raw, CONTENT_WIDTH - 28, 9.5, mono=True))
        line_height = 13.5
        height = len(wrapped_lines) * line_height + 18 + (16 if label else 0)
        self.ensure_space(height + 6)
        box_top = self.cursor_y + 4
        box_bottom = self.cursor_y - height + 4
        assert self.page is not None
        self.page.rects.append(Rect(LEFT_MARGIN, box_bottom, CONTENT_WIDTH, height, COLORS["panel_alt"]))
        if label:
            self.add_text_line(label, LEFT_MARGIN + 12, self.cursor_y - 2, FONT_MAP["body_bold"], 9.5, COLORS["muted"])
            self.cursor_y -= 18
        y = self.cursor_y - 2
        for line in wrapped_lines:
            self.add_text_line(line, LEFT_MARGIN + 12, y, FONT_MAP["mono"], 9.5, COLORS["ink"])
            y -= line_height
        self.cursor_y = box_bottom - 10

    def add_status_table(self, rows: list[tuple[str, str]]) -> None:
        for code, description in rows:
            wrapped = wrap_text(description, CONTENT_WIDTH - 92, 10.2)
            needed = max(32, len(wrapped) * 13.5 + 12)
            self.ensure_space(needed + 4)
            box_bottom = self.cursor_y - needed + 6
            assert self.page is not None
            self.page.rects.append(Rect(LEFT_MARGIN, box_bottom, CONTENT_WIDTH, needed, COLORS["panel"]))
            self.add_text_line(code, LEFT_MARGIN + 12, self.cursor_y - 12, FONT_MAP["body_bold"], 10.6, COLORS["brand"])
            line_y = self.cursor_y - 12
            for line in wrapped:
                self.add_text_line(line, LEFT_MARGIN + 96, line_y, FONT_MAP["body"], 10.2, COLORS["ink"])
                line_y -= 13.5
            self.cursor_y = box_bottom - 8

    def add_endpoint_entry(
        self,
        method: str,
        path: str,
        summary: str,
        auth: str,
        description: str,
        parameters: list[str],
        request_fields: list[str],
        response_fields: list[str],
        response_codes: list[str],
        notes: list[str],
        example: str | None,
    ) -> None:
        """Render an endpoint with conservative flow layout.

        The earlier card layout tried to estimate a whole endpoint block height
        up front. Long schemas and examples can make that estimate drift. This
        renderer writes each subsection sequentially and lets every paragraph,
        list, and code block handle its own page break.
        """
        self.ensure_space(88)
        assert self.page is not None

        self.page.lines.append(Line(LEFT_MARGIN, self.cursor_y + 10, A4_WIDTH - RIGHT_MARGIN, self.cursor_y + 10, COLORS["rule"], 1))
        self.cursor_y -= 4

        badge_color = METHOD_COLORS.get(method, COLORS["purple"])
        self.page.rects.append(Rect(LEFT_MARGIN, self.cursor_y - 16, 54, 23, badge_color))
        self.add_text_line(method, LEFT_MARGIN + 11, self.cursor_y - 8, FONT_MAP["body_bold"], 10.2, (1, 1, 1))

        path_lines = wrap_text(path, CONTENT_WIDTH - 70, 10.7, mono=True)
        path_y = self.cursor_y - 5
        for line in path_lines:
            self.add_text_line(line, LEFT_MARGIN + 68, path_y, FONT_MAP["mono_bold"], 10.7, COLORS["ink"])
            path_y -= 14
        self.cursor_y = min(self.cursor_y - 30, path_y - 2)

        if summary:
            self.add_paragraph(summary, size=10.4, color=COLORS["muted"], width=CONTENT_WIDTH - 68, x=LEFT_MARGIN + 68)

        self.add_key_value_list([("Auth", auth)])
        if description:
            self.add_paragraph(description, size=10.4)

        def labeled_list(title: str, items: list[str], *, size: float = 9.9) -> None:
            if not items:
                return
            self.ensure_space(32)
            self.add_text_line(title, LEFT_MARGIN, self.cursor_y, FONT_MAP["body_bold"], 11.2, COLORS["brand"])
            self.cursor_y -= 16
            self.add_bullets(items, size=size, indent=16)
            self.cursor_y -= 2

        labeled_list("Parameters", parameters)
        labeled_list("Request Body", request_fields)
        labeled_list("Response Body", response_fields)
        labeled_list("Status Codes", response_codes)
        labeled_list("Notes", notes, size=9.7)

        if example:
            self.add_code_block(example, label="Example")

        self.cursor_y -= 16

    def add_endpoint_card(
        self,
        method: str,
        path: str,
        summary: str,
        auth: str,
        description: str,
        parameters: list[str],
        request_fields: list[str],
        response_fields: list[str],
        response_codes: list[str],
        notes: list[str],
        example: str | None,
    ) -> None:
        desc_lines = wrap_text(description, CONTENT_WIDTH - 24, 10.6)
        param_lines = []
        for item in parameters:
            param_lines.extend(wrap_text(item, CONTENT_WIDTH - 34, 10.0))
        request_lines = []
        for item in request_fields:
            request_lines.extend(wrap_text(item, CONTENT_WIDTH - 34, 10.0))
        response_lines = []
        for item in response_fields:
            response_lines.extend(wrap_text(item, CONTENT_WIDTH - 34, 10.0))
        note_lines = []
        for item in notes:
            note_lines.extend(wrap_text(item, CONTENT_WIDTH - 34, 9.8))

        code_lines = wrap_text(example, CONTENT_WIDTH - 28, 8.8, mono=True) if example else []
        estimated_height = (
            54
            + len(desc_lines) * 14
            + (len(param_lines) * 13 + 16 if param_lines else 0)
            + (len(request_lines) * 13 + 16 if request_lines else 0)
            + (len(response_lines) * 13 + 16 if response_lines else 0)
            + (len(note_lines) * 13 + 16 if note_lines else 0)
            + (len(code_lines) * 12 + 24 if code_lines else 0)
        )
        self.ensure_space(estimated_height + 12)

        assert self.page is not None
        box_bottom = self.cursor_y - estimated_height + 10
        self.page.rects.append(Rect(LEFT_MARGIN, box_bottom, CONTENT_WIDTH, estimated_height, COLORS["panel"]))
        self.page.rects.append(Rect(LEFT_MARGIN, self.cursor_y - 32, CONTENT_WIDTH, 42, COLORS["brand_soft"]))

        badge_color = METHOD_COLORS.get(method, COLORS["purple"])
        self.page.rects.append(Rect(LEFT_MARGIN + 12, self.cursor_y - 22, 48, 22, badge_color))
        self.add_text_line(method, LEFT_MARGIN + 22, self.cursor_y - 15, FONT_MAP["body_bold"], 10, (1, 1, 1))
        self.add_text_line(path, LEFT_MARGIN + 72, self.cursor_y - 13, FONT_MAP["mono_bold"], 10.4, COLORS["ink"])
        self.add_text_line(summary, LEFT_MARGIN + 72, self.cursor_y - 28, FONT_MAP["body"], 10.2, COLORS["muted"])

        cursor = self.cursor_y - 52
        self.add_text_line("Auth", LEFT_MARGIN + 12, cursor, FONT_MAP["body_bold"], 10.2, COLORS["brand"])
        self.add_text_line(auth, LEFT_MARGIN + 52, cursor, FONT_MAP["body"], 10.2, COLORS["ink"])
        cursor -= 16

        for line in desc_lines:
            self.add_text_line(line, LEFT_MARGIN + 12, cursor, FONT_MAP["body"], 10.6, COLORS["ink"])
            cursor -= 14

        def render_list(title: str, items: list[str], *, mono: bool = False) -> None:
            nonlocal cursor
            if not items:
                return
            self.add_text_line(title, LEFT_MARGIN + 12, cursor, FONT_MAP["body_bold"], 10.1, COLORS["brand"])
            cursor -= 14
            for item in items:
                font = FONT_MAP["mono"] if mono else FONT_MAP["body"]
                self.add_text_line("-", LEFT_MARGIN + 16, cursor, FONT_MAP["body_bold"], 10.1, COLORS["muted"])
                self.add_text_line(item, LEFT_MARGIN + 30, cursor, font, 9.9, COLORS["ink"])
                cursor -= 13
            cursor -= 3

        render_list("Parameters", param_lines)
        render_list("Request Body", request_lines)
        render_list("Response", response_lines)
        render_list("Status Codes", response_codes)
        render_list("Notes", note_lines)

        if code_lines:
            code_height = len(code_lines) * 12 + 18
            self.page.rects.append(Rect(LEFT_MARGIN + 12, cursor - code_height + 4, CONTENT_WIDTH - 24, code_height, COLORS["panel_alt"]))
            self.add_text_line("Example", LEFT_MARGIN + 24, cursor - 8, FONT_MAP["body_bold"], 9.8, COLORS["muted"])
            code_y = cursor - 23
            for line in code_lines:
                self.add_text_line(line, LEFT_MARGIN + 24, code_y, FONT_MAP["mono"], 8.8, COLORS["ink"])
                code_y -= 12
            cursor -= code_height + 4

        self.cursor_y = box_bottom - 12


def resolve_schema(schema: dict[str, Any], components: dict[str, Any]) -> dict[str, Any]:
    if "$ref" in schema:
        name = schema["$ref"].split("/")[-1]
        return components[name]
    return schema


def schema_fields(name: str, components: dict[str, Any]) -> list[str]:
    schema = components[name]
    props = schema.get("properties", {})
    required = set(schema.get("required", []))
    lines = []
    for field_name, field_schema in props.items():
        field_type = human_type(field_schema)
        requirement = "required" if field_name in required else "optional"
        description = field_schema.get("description")
        suffix = f" - {clean_text(description)}" if description else ""
        lines.append(f"{field_name}: {field_type} ({requirement}){suffix}")
    return lines


def paged_response_fields(name: str, components: dict[str, Any]) -> list[str]:
    schema = components[name]
    fields = []
    for field_name, field_schema in schema.get("properties", {}).items():
        fields.append(f"{field_name}: {human_type(field_schema)}")
    return fields


def group_operations(openapi: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for path, methods in openapi["paths"].items():
        if not path.startswith(settings.API_V1_PREFIX):
            continue
        for method, operation in methods.items():
            tags = operation.get("tags") or ["General"]
            tag = tags[0]
            grouped.setdefault(tag, []).append(
                {
                    "method": method.upper(),
                    "path": path,
                    "operation": operation,
                }
            )
    order = ["Authentication", "Drivers", "Teams", "Circuits", "Races", "Results", "Analytics"]
    return {key: sorted(grouped.get(key, []), key=lambda item: (item["path"], item["method"])) for key in order if key in grouped}


def build_document() -> PDFBuilder:
    openapi = get_openapi_schema()
    components = openapi.get("components", {}).get("schemas", {})
    grouped = group_operations(openapi)

    operation_count = sum(len(items) for items in grouped.values())
    analytics_count = len(grouped.get("Analytics", []))

    doc = PDFBuilder()
    layout = Layout(doc)
    layout.add_title_page(
        [
            ("Version", settings.PROJECT_VERSION),
            ("HTTP operations", str(operation_count)),
            ("Analytics endpoints", str(analytics_count)),
            ("Security", "JWT access + refresh"),
            ("Runtime docs", "/docs, /redoc, /openapi.json"),
            ("Verified checks", "Django check + acceptance suite passed"),
        ]
    )

    layout.add_section_heading(
        "Overview",
        "F1 Analytics API is a RESTful service for Formula 1 data exploration. "
        "It combines full CRUD coverage for primary resources with a dedicated "
        "analytics layer for season trends, constructor standings, circuit "
        "history, and head-to-head driver comparisons.",
    )
    layout.add_key_value_list(
        [
            ("Application", openapi["info"]["title"]),
            ("Version", openapi["info"]["version"]),
            ("Base prefix", settings.API_V1_PREFIX),
            ("OpenAPI schema", "/openapi.json"),
            ("Interactive docs", "/docs and /redoc"),
            ("Primary stack", "FastAPI, Pydantic, SQLAlchemy, Django adapter, SQLite (verified), MySQL-ready config"),
            ("Authentication", "Form/JSON login + JWT bearer tokens"),
            ("Rate limiting", f"{settings.RATE_LIMIT_PER_MINUTE} requests per minute per IP"),
            ("Caching", "TTL cache for analytics queries (10-30 minutes)"),
            ("Deployment", "WSGI-compatible Django adapter with collectstatic support"),
        ]
    )
    layout.add_subheading("Domain Model")
    layout.add_bullets(
        [
            "drivers, teams, circuits, and races are primary resource collections exposed via CRUD endpoints.",
            "results is the central fact table that links drivers, constructors, and races and remains read-only through the API.",
            "analytics endpoints aggregate results into season, circuit, team, and driver insights without changing source data.",
        ]
    )
    layout.add_subheading("Status and Error Conventions")
    layout.add_status_table(STATUS_NOTES)

    layout.add_section_heading(
        "Authentication Flow",
        "Write operations require a bearer access token. The login endpoint issues "
        "both access and refresh tokens, while the refresh endpoint rotates only "
        "the access token so the client can continue without re-entering credentials.",
    )
    layout.add_bullets(
        [
            f"Register a user with POST {settings.API_V1_PREFIX}/auth/register.",
            f"Login with POST {settings.API_V1_PREFIX}/auth/login (form fields) or POST {settings.API_V1_PREFIX}/auth/login/json (JSON body).",
            f"Send Authorization: Bearer <access_token> for protected write endpoints and GET {settings.API_V1_PREFIX}/auth/me.",
            f"Use POST {settings.API_V1_PREFIX}/auth/refresh to exchange a valid refresh token for a new access token.",
        ]
    )
    layout.add_code_block(
        f"""
POST {settings.API_V1_PREFIX}/auth/register
POST {settings.API_V1_PREFIX}/auth/login
Authorization: Bearer <access_token>
POST {settings.API_V1_PREFIX}/auth/refresh
        """,
        label="Auth sequence",
    )

    for group, items in grouped.items():
        layout.add_section_heading(group, GROUP_INTROS.get(group))
        if group == "Analytics":
            layout.add_bullets(
                [
                    "All analytics endpoints are public and read-only.",
                    "Results are cached internally to speed up repeated aggregate queries.",
                    "Analytics responses are declared with Pydantic response models and supplemented below with service-layer examples.",
                ]
            )

        for item in items:
            method = item["method"]
            path = item["path"]
            operation = item["operation"]
            description = clean_text(operation.get("description") or operation.get("summary") or "")
            parameters = []
            for parameter in operation.get("parameters", []):
                location = parameter.get("in", "query")
                required = "required" if parameter.get("required") else "optional"
                schema = parameter.get("schema", {})
                param_type = human_type(schema)
                desc = clean_text(parameter.get("description") or "")
                line = f"{parameter['name']} [{location}] - {param_type}, {required}"
                if desc:
                    line += f" - {desc}"
                parameters.append(line)

            request_fields: list[str] = []
            request_body = operation.get("requestBody")
            if request_body:
                content = request_body.get("content", {})
                for media_type, media_info in content.items():
                    schema = media_info.get("schema", {})
                    if "$ref" in schema:
                        ref_name = schema["$ref"].split("/")[-1]
                        request_fields.append(f"Content-Type: {media_type}")
                        request_fields.extend(schema_fields(ref_name, components))
                    else:
                        request_fields.append(f"Content-Type: {media_type}")
                        request_fields.append(f"Schema: {human_type(schema)}")

            response_codes = []
            response_fields: list[str] = []
            for code, response in operation.get("responses", {}).items():
                response_codes.append(f"{code} - {clean_text(response.get('description', 'Response'))}")
                content = response.get("content", {})
                if code.startswith("2") and content:
                    media_info = next(iter(content.values()))
                    schema = media_info.get("schema", {})
                    if "$ref" in schema:
                        ref_name = schema["$ref"].split("/")[-1]
                        if ref_name.startswith("PagedResponse_"):
                            response_fields.extend(paged_response_fields(ref_name, components))
                        else:
                            response_fields.extend(schema_fields(ref_name, components))
                    elif schema:
                        response_fields.append(f"schema: {human_type(schema)}")

            manual = ANALYTICS_DETAILS.get((method, path))
            notes: list[str] = []
            example: str | None = None
            if manual:
                response_fields = manual["response_fields"]
                notes.extend(manual["notes"])
                example = pretty_json(manual["example"])
            elif path == f"{settings.API_V1_PREFIX}/auth/login":
                notes.extend(
                    [
                        "Swagger UI can submit the form-field variant of login.",
                        "Successful login returns access_token, refresh_token, token_type, and expires_in.",
                    ]
                )
                example = pretty_json(
                    {
                        "access_token": "<jwt>",
                        "refresh_token": "<jwt>",
                        "token_type": "bearer",
                        "expires_in": 1800,
                    }
                )
            elif path == f"{settings.API_V1_PREFIX}/auth/refresh":
                example = pretty_json(
                    {
                        "access_token": "<jwt>",
                        "token_type": "bearer",
                        "expires_in": 1800,
                    }
                )
            elif path.endswith("/drivers") and method == "GET":
                notes.append("List endpoints return a shared pagination envelope with items, total, page, limit, pages, has_next, and has_prev.")
            elif group in {"Drivers", "Teams", "Circuits", "Races", "Results"} and method == "GET":
                notes.append("This response is produced by the shared FastAPI implementation used by both direct ASGI and Django-adapted deployments.")

            auth = "Bearer token required" if operation.get("security") else "Public"
            layout.add_endpoint_entry(
                method=method,
                path=path,
                summary=clean_text(operation.get("summary") or ""),
                auth=auth,
                description=description,
                parameters=parameters,
                request_fields=request_fields,
                response_fields=response_fields,
                response_codes=response_codes,
                notes=notes,
                example=example,
            )

    layout.add_section_heading(
        "Deployment Appendix",
        "The Django layer is a thin WSGI deployment adapter around the same FastAPI "
        "core used for direct ASGI execution, so routes, auth, docs, and analytics "
        "stay aligned across both entrypoints.",
    )
    layout.add_bullets(
        [
            "API_V1_PREFIX controls Django route mounting, FastAPI router prefixes, and frontend API requests.",
            "collectstatic writes production assets to STATIC_ROOT for web-server or PythonAnywhere static mappings.",
            "FastAPI startup runs Alembic migrations automatically through app/database_migrations.py.",
            "Django can still adopt an existing SQLite database with migrate --fake-initial so its app registry matches the already-migrated schema.",
        ]
    )
    layout.add_code_block(
        """
python manage.py check

# FastAPI / shared schema entrypoint
python -m uvicorn app.main:app --reload

# Django deployment adapter
python manage.py migrate --fake-initial
python manage.py collectstatic --noinput
python manage.py runserver 127.0.0.1:8001
        """,
        label="Django deployment checklist",
    )

    layout.add_section_heading(
        "Testing and Reliability",
        "The repository includes a Django acceptance suite that exercises "
        "authentication, CRUD resources, results filtering, all six analytics endpoints, "
        "runtime docs, and the static frontend entrypoint.",
    )
    layout.add_bullets(
        [
            "The acceptance script copies f1_analytics.db into a temporary SQLite database so local data is not mutated.",
            "manage.py check and the shared OpenAPI export both run cleanly with the current Django settings.",
            "The browser-facing page, /static/app.js, /docs, /redoc, /openapi.json, and /health are verified before API flows.",
        ]
    )
    layout.add_code_block(
        """
source venv/bin/activate
python manage.py check
python scripts/django_openapi.py --file /tmp/f1_openapi.json
python scripts/verify_django_acceptance.py

# Current verified result:
# Django acceptance verification passed
        """,
        label="Verification",
    )

    return doc


def main() -> None:
    document = build_document()
    document.build(OUTPUT_PATH)
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
