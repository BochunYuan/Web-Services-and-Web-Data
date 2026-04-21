#!/usr/bin/env python3
"""
Generate a formal supplementary PDF for the GenAI declaration, analysis,
and conversation log appendix required by the coursework brief.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = ROOT / "docs" / "genai_conversation_logs_appendix.pdf"
sys.path.insert(0, str(ROOT))

from scripts.generate_api_documentation_pdf import (
    COLORS,
    CONTENT_WIDTH,
    FONT_MAP,
    LEFT_MARGIN,
    RIGHT_MARGIN,
    A4_HEIGHT,
    A4_WIDTH,
    Layout,
    Line,
    PDFBuilder,
    Rect,
    TextRun,
    wrap_text,
)


class AppendixLayout(Layout):
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
                A4_WIDTH - RIGHT_MARGIN - 195,
                A4_HEIGHT - 34,
                "GenAI Appendix / Supplementary Material",
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

    def add_title_page(self) -> None:
        assert self.page is not None
        top_box_y = A4_HEIGHT - 314
        top_box_height = 228
        self.page.rects.append(Rect(LEFT_MARGIN, top_box_y, CONTENT_WIDTH, top_box_height, COLORS["brand_soft"]))
        self.page.texts.append(
            TextRun(LEFT_MARGIN + 30, top_box_y + 164, "GenAI Declaration,", FONT_MAP["body_bold"], 24, COLORS["brand"])
        )
        self.page.texts.append(
            TextRun(LEFT_MARGIN + 30, top_box_y + 134, "Analysis, and Conversation Logs", FONT_MAP["body_bold"], 24, COLORS["brand"])
        )
        self.page.texts.append(
            TextRun(LEFT_MARGIN + 30, top_box_y + 106, "Supplementary Appendix", FONT_MAP["body_bold"], 18, COLORS["ink"])
        )

        intro = (
            "This document accompanies the technical report and responds to the "
            "brief requirement to declare GenAI use, analyse that use, and attach "
            "examples of exported conversation logs as supplementary material."
        )
        y = top_box_y + 72
        for line in wrap_text(intro, CONTENT_WIDTH - 60, 11.4):
            self.page.texts.append(TextRun(LEFT_MARGIN + 30, y, line, FONT_MAP["body"], 11.4, COLORS["ink"]))
            y -= 15

        self.page.texts.append(
            TextRun(
                LEFT_MARGIN,
                88,
                "Module: XJCO3011 Web Services and Web Data    Project: F1 Analytics API",
                FONT_MAP["body"],
                10,
                COLORS["muted"],
            )
        )
        self.page.texts.append(
            TextRun(
                LEFT_MARGIN,
                68,
                "Status: supplementary submission-ready appendix generated from repository evidence",
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
        label_width: float = 160,
        size: float = 10.0,
        row_gap: float = 3,
    ) -> None:
        leading = size + 4.0
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
    doc = PDFBuilder()
    layout = AppendixLayout(doc)
    layout.add_title_page()

    layout.add_section_heading(
        "Brief Alignment",
        "The coursework brief states that GenAI use must be declared and that "
        "examples of exported conversation logs should be attached as supplementary material.",
    )
    layout.add_bullets(
        [
            "Page 1: the brief permits GenAI as a primary tool but requires all tools and purposes to be declared.",
            "Page 6: some examples of exported conversation logs must be attached as supplementary material.",
            "Page 18: the submission requirements explicitly list GenAI declaration, analysis, and conversation logs as an appendix.",
        ],
        size=10.0,
    )
    layout.add_paragraph(
        "This appendix is therefore structured to satisfy all three elements: "
        "declaration, analysis, and conversation-log evidence.",
        size=10.3,
    )

    layout.add_section_heading(
        "Academic Integrity Note",
        "Transparency requires a clear distinction between curated evidence and raw platform exports.",
    )
    layout.add_paragraph(
        "This appendix is a curated and structured record of GenAI use. It does "
        "not claim to be a complete platform-native transcript export. Instead, "
        "it organises representative prompt themes, implementation outcomes, and "
        "verification steps in a form suitable for submission and oral defence.",
        size=10.1,
    )
    layout.add_bullets(
        [
            "If raw exported chat files are available, they should be submitted alongside this appendix.",
            "This document should not be misrepresented as an unedited full transcript if it is not one.",
            "Its role is to support honest disclosure and make the author's use of GenAI intelligible to the marker.",
        ],
        size=9.9,
    )

    layout.add_section_heading(
        "Tool Declaration",
        "Only one GenAI tool is evidenced in the repository declaration, and its purposes are specific rather than vague.",
    )
    layout.add_bullets(
        [
            "Claude (Anthropic, claude-sonnet-4.6): architecture exploration, implementation guidance, debugging, and documentation support.",
            "GenAI was used throughout the assessment in a declared manner, consistent with the Green Light brief policy.",
        ],
        size=10.0,
    )

    layout.add_section_heading(
        "Method of Use",
        "The project used GenAI as a technical collaborator rather than as a replacement for judgment.",
    )
    layout.add_bullets(
        [
            "Ask for alternatives or explanations.",
            "Compare the answer with project constraints and coursework goals.",
            "Implement an adapted solution rather than copying blindly.",
            "Verify with tests, runtime checks, or documentation review.",
        ],
        size=10.0,
    )

    layout.add_section_heading(
        "Conversation Log Register",
        "Representative conversations are grouped by engineering purpose so the evidence is easier to audit.",
    )
    register_rows = [
        ("CL-01 Framework choice", "FastAPI vs Django for an API with auto-generated documentation."),
        ("CL-02 Async database design", "SQLAlchemy async vs sync and event-loop implications."),
        ("CL-03 Schema modelling", "Star-schema suitability for race results analytics."),
        ("CL-04 Authentication", "Why dual JWT tokens are preferable to one long-lived token."),
        ("CL-05 Defensive security", "Timing attacks and dummy-hash mitigation for login."),
        ("CL-06 Aggregation logic", "Conditional aggregation for wins and grouped metrics."),
        ("CL-07 Self-join analytics", "Using aliased() for head-to-head driver comparison."),
        ("CL-08 DNF handling", "Why position_order is better than nullable position."),
        ("CL-09 Test strategy", "Dependency overrides and fixture scope choices in FastAPI tests."),
        ("CL-10 MCP design", "How tool descriptions should guide an LLM effectively."),
        ("CL-11 Dependency debugging", "bcrypt/passlib compatibility diagnosis."),
        ("CL-12 Import cleaning", "Handling Ergast null markers such as \\N in CSV data."),
    ]
    layout.add_key_value_list(register_rows, label_width=176, size=9.8, row_gap=3)

    layout.add_section_heading(
        "Representative Extracts",
        "These are thematic summaries of the kinds of conversations that shaped implementation decisions.",
    )
    layout.add_subheading("A. Architecture")
    layout.add_paragraph(
        "GenAI was asked to compare FastAPI and Django in the context of an "
        "assessed REST API. The response highlighted FastAPI's automatic "
        "OpenAPI generation and stronger fit for typed API development. The "
        "author then selected FastAPI and built the project around its API-first workflow.",
        size=9.9,
    )
    layout.add_subheading("B. Security")
    layout.add_paragraph(
        "GenAI was used to reason about access and refresh token separation and "
        "to understand timing-attack risks in login flows. The implementation "
        "adopted a dual-token JWT design and added dummy-hash checking for "
        "unknown users after independent review.",
        size=9.9,
    )
    layout.add_subheading("C. Analytics")
    layout.add_paragraph(
        "For analytical endpoints, GenAI helped explain conditional aggregation "
        "and self-join patterns. Those patterns were translated into SQLAlchemy "
        "queries and then checked against automated tests and expected F1 semantics.",
        size=9.9,
    )
    layout.add_subheading("D. Debugging")
    layout.add_paragraph(
        "GenAI was also used to diagnose real implementation problems such as "
        "bcrypt version incompatibility and dataset null cleaning. These were "
        "not accepted on trust alone; they were implemented, tested, and documented.",
        size=9.9,
    )

    layout.add_section_heading(
        "Analysis of Quality of Use",
        "The brief rewards thoughtful and creative use of GenAI, so the relevant question is not only whether AI was used, but how.",
    )
    layout.add_bullets(
        [
            "The prompts were often high-level and exploratory rather than limited to syntax completion.",
            "The repository reflects explanation-led use: architecture, security, analytics, testing, and debugging all show traceable reasoning.",
            "The final implementation includes author-selected trade-offs such as F1 domain choice, in-process caching, and discovery-first MCP tools.",
            "Use was declared openly rather than hidden, which is essential under the brief's academic misconduct warning.",
        ],
        size=9.9,
    )

    layout.add_section_heading(
        "Author Judgment and Verification",
        "Independent judgment remained necessary in both design and acceptance of suggestions.",
    )
    layout.add_bullets(
        [
            "Choosing the F1 analytics domain and deciding which endpoints would show genuine analytical depth.",
            "Balancing architectural ambition with coursework practicality, for example using cachetools rather than Redis.",
            "Designing compact but expressive seed data for tests.",
            "Running tests and local checks before accepting or documenting a change.",
        ],
        size=10.0,
    )

    layout.add_section_heading(
        "Submission Guidance",
        "This appendix is intended to be read together with the technical report and any raw exported chat files available to the student.",
    )
    layout.add_bullets(
        [
            "Technical report: concise GenAI declaration and analysis inside the five-page limit.",
            "This appendix: expanded declaration, analysis, and representative conversation-log register.",
            "Optional raw exports: platform-native chat exports, if available, to be attached as additional supplementary evidence.",
        ],
        size=10.0,
    )
    layout.add_paragraph(
        "Repository locations: `docs/genai_conversation_logs_appendix.md`, "
        "`docs/genai_conversation_logs_appendix.pdf`, `docs/technical_report.pdf`, and `AGENTS.md`.",
        size=9.9,
    )
    return doc


if __name__ == "__main__":
    doc = build_document()
    doc.build(OUTPUT_PATH)
    print(f"Wrote {OUTPUT_PATH}")
