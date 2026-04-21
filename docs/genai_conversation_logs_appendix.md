# GenAI Declaration, Analysis, and Conversation Logs Appendix

**Module:** XJCO3011 Web Services and Web Data  
**Project:** F1 Analytics API  
**Submission:** Coursework 1  
**Document type:** Supplementary material / appendix

## Purpose of this appendix

This appendix is submitted in response to the brief requirement to:

1. declare all GenAI tools used and their purposes;
2. provide analysis of how GenAI was used; and
3. attach some examples of exported conversation logs as supplementary material.

The coursework brief states that this is a Green Light assessment and explicitly permits substantial GenAI use, including use as a primary tool, provided that such use is declared transparently and supported with supplementary evidence.

## Important academic integrity note

This appendix is a structured record of GenAI use prepared from the repository evidence, the author's declared workflow, and representative prompt summaries. It is intended to support transparent disclosure and oral examination preparation.

Where platform-native raw exported chat transcripts are available, they should be submitted alongside this appendix as additional evidence. This appendix does **not** claim to be a byte-for-byte platform export of every conversation. Instead, it provides:

- a formal declaration of tools and purposes;
- a methodologically organised log of representative conversations;
- selected prompt/response summaries showing how GenAI informed development;
- explicit statements of human judgment, verification, and adaptation.

This distinction matters academically: curated logs and analytical summaries can support transparency, but they should not be misrepresented as unedited raw platform exports if they are not.

## Tools used

| Tool | Version / model | Primary purpose |
|---|---|---|
| Claude (Anthropic) | claude-sonnet-4.6 | Architecture exploration, implementation guidance, debugging, documentation drafting |

## Summary of permitted and actual use

GenAI was used throughout the lifecycle of the project in a declared and methodologically structured way. Its role was that of a technical collaborator rather than an autonomous replacement for software engineering judgment. Typical use cases included:

- exploring framework and architecture alternatives before implementation;
- understanding SQLAlchemy async patterns and schema design trade-offs;
- discussing secure authentication design and defensive API behaviour;
- refining non-trivial analytics query patterns;
- diagnosing library incompatibilities and validation issues;
- improving documentation quality and structure.

The final code, tests, and written materials were reviewed and adapted for project-specific constraints. Suggestions were not accepted automatically; they were evaluated, tested, and sometimes modified or rejected.

## Methodological statement

The brief associates higher marks with thoughtful, creative, and high-level GenAI use rather than arbitrary or hidden use. In that spirit, GenAI use in this project followed a repeated pattern:

1. identify a design or implementation question;
2. ask GenAI for alternatives, trade-offs, or explanations;
3. compare suggestions against project constraints;
4. implement an adapted version in the repository;
5. validate through tests, runtime checks, or documentation review.

This process means GenAI contributed to understanding and exploration, while responsibility for integration and final decisions remained with the author.

## Conversation log register

The following register summarises representative conversations used during development. These entries correspond to the declared uses in the project and are organised by engineering purpose rather than by platform timestamp alone.

| Log ID | Theme | Representative user prompt | What GenAI contributed | What the author decided / verified |
|---|---|---|---|---|
| CL-01 | Framework selection | "Should I use FastAPI or Django for a REST API that needs auto-generated documentation?" | Compared framework strengths, especially FastAPI's built-in OpenAPI generation | Chose FastAPI because it matched the API-first brief and reduced documentation maintenance |
| CL-02 | Async database architecture | "What is the difference between SQLAlchemy 2.0 async vs sync, and which is better for FastAPI?" | Explained event-loop implications and async integration benefits | Adopted async SQLAlchemy with `create_async_engine` and `aiosqlite` |
| CL-03 | Data modelling | "What is a star schema and is it the right pattern for race results data?" | Explained fact-table plus dimension-table design | Chose `results` as the fact table linked to drivers, teams, races, and circuits |
| CL-04 | Authentication design | "Why use two tokens (access + refresh) instead of one long-lived token?" | Clarified security trade-offs of dual-token JWT design | Implemented access and refresh token flow rather than a single long-lived token |
| CL-05 | Timing-attack defence | "What is a timing attack and how does it apply to login endpoints?" | Explained username enumeration risk and constant-time mitigation | Added dummy-hash checking in authentication flow |
| CL-06 | Analytics aggregation | "How do I count race wins within a GROUP BY query without a subquery?" | Introduced conditional aggregation with `COUNT(CASE WHEN ...)` | Applied this pattern in analytics queries and validated outputs with tests |
| CL-07 | Self-join analytics | "How do I join the same table twice in SQLAlchemy to compare two drivers?" | Explained `aliased()` for self-joins | Used aliased results tables in head-to-head comparison endpoint |
| CL-08 | DNF interpretation | "How do I handle DNFs correctly in head-to-head comparisons?" | Suggested using `position_order` rather than nullable finishing position | Integrated this rule into comparison logic because it better matched F1 semantics |
| CL-09 | FastAPI testing | "How do I make FastAPI use a different database in tests without changing application code?" | Explained dependency overrides and fixture patterns | Implemented isolated test database setup in `tests/conftest.py` |
| CL-10 | MCP tool design | "What makes MCP tool descriptions useful to an LLM?" | Recommended stronger preconditions and parameter semantics | Refined MCP tool descriptions and discovery workflow |
| CL-11 | Dependency debugging | "Why is passlib failing with bcrypt?" | Identified version incompatibility and a stable package pin | Pinned `bcrypt==4.0.1` and documented the reason |
| CL-12 | Data import cleaning | "How should Ergast CSV null markers like \\N be handled?" | Proposed explicit null-string normalisation logic | Added `NULL_STRINGS` and conversion helpers in `import_data.py` |

## Representative conversation extracts

The following extracts are intentionally short and thematic. They are not intended to replace full platform exports; instead, they show the character of the interactions and the way they influenced implementation.

### Extract A: Framework and architecture exploration

**Prompt summary:** The author asked whether FastAPI or Django would be better for an assessed REST API that required strong documentation support and modern API ergonomics.

**GenAI contribution:** The answer highlighted FastAPI's automatic OpenAPI generation, better alignment with typed request/response models, and lower overhead for an API-only submission.

**Outcome in the project:** The repository uses FastAPI with auto-generated Swagger UI and ReDoc, and the written documentation treats this as a deliberate stack justification rather than an accidental convenience.

### Extract B: Authentication and security reasoning

**Prompt summary:** The author asked why a dual-token access and refresh workflow is preferable to a single long-lived JWT.

**GenAI contribution:** The answer emphasised containment of damage if an access token is stolen and the separation of short-lived request credentials from longer-lived refresh credentials.

**Outcome in the project:** The authentication subsystem implements dual-token JWT flow, and the technical report discusses this as part of the project's security maturity.

### Extract C: SQL analytics design

**Prompt summary:** The author asked how to express race wins, grouped statistics, and head-to-head comparisons in SQLAlchemy without writing raw SQL strings.

**GenAI contribution:** The answer suggested conditional aggregation and SQLAlchemy table aliasing for self-joins.

**Outcome in the project:** These techniques appear directly in the analytics service and are now covered by automated tests.

### Extract D: Debugging dependency and data issues

**Prompt summary:** The author asked why bcrypt integration was breaking and how to correctly process Ergast null markers such as `\\N`.

**GenAI contribution:** The answer identified a library compatibility issue and recommended normalising a wider set of null representations in the import pipeline.

**Outcome in the project:** The requirements file pins a compatible bcrypt version, and the import script now has explicit null-cleaning helpers with tests.

## Analysis of GenAI usage quality

The brief links stronger marks not merely to using GenAI often, but to using it creatively and at a high level. This appendix therefore distinguishes between superficial and substantive use.

### Why this use is methodologically sound

- GenAI was used to understand alternatives and trade-offs, not only to request finished code.
- The prompts often addressed architecture, security, analytics logic, or debugging strategy rather than low-level syntax alone.
- Outputs were checked against project constraints such as PythonAnywhere deployment simplicity, FastAPI idioms, SQLAlchemy behaviour, and coursework deliverables.
- Repository changes were validated through tests and runtime checks.

### Why this use is not merely arbitrary

- The same themes recur across the codebase and documents: architecture, security, analytics, testing, MCP tooling, and debugging.
- The declared prompts align with observable implementation choices in the repository.
- Several decisions explicitly required human judgment beyond the AI suggestion, such as choosing F1 as the domain, preferring cachetools over Redis, and selecting head-to-head comparison as an analytically richer endpoint.

### Limits and caution

- GenAI explanations can be persuasive while still being incomplete or library-version-sensitive.
- Some advice was accepted only after validation or adaptation.
- Any raw exported platform logs submitted separately should be treated as evidential supplements, not as substitutes for critical judgment.

## Author judgment and verification

To make the division of responsibility academically explicit, the following areas required independent author judgment:

1. **Problem framing:** choosing the F1 analytics domain and shaping the scope into a coherent API project.
2. **Feature selection:** choosing the specific analytics endpoints, especially the head-to-head comparison.
3. **Pragmatic infrastructure decisions:** retaining in-process caching rather than introducing Redis for a single-server coursework deployment.
4. **Testing strategy:** designing a compact but expressive seed dataset that exercises multiple analytics paths.
5. **Acceptance and rejection of suggestions:** only integrating advice that matched the project's actual behaviour and could be validated.

Verification activities included:

- running the automated test suite;
- inspecting API responses through local execution;
- checking generated documentation;
- confirming that implementation details matched the declared design rationale.

## Relationship to the technical report

The technical report contains the required concise GenAI declaration and analysis within the five-page limit. This appendix exists so that the submission also satisfies the brief's supplementary evidence requirement without overloading the report body.

The intended relationship is:

- **technical report:** concise declaration and evaluative discussion;
- **this appendix:** fuller record of tools, purposes, representative log entries, and evidence framing;
- **optional raw exported chat files:** platform-native exports, if separately available.

## Submission note

If raw platform-exported conversation files are available, they should be submitted together with this appendix and named clearly, for example:

- `supplementary/raw_exports/claude_export_01.pdf`
- `supplementary/raw_exports/claude_export_02.pdf`

This appendix should then be read as the explanatory guide to those raw files rather than as a replacement for them.

## File index for this submission

- Technical report with concise GenAI declaration: `docs/technical_report.pdf`
- Supplementary appendix source: `docs/genai_conversation_logs_appendix.md`
- Supplementary appendix PDF: `docs/genai_conversation_logs_appendix.pdf`
- Existing repository GenAI declaration source used to prepare this appendix: `AGENTS.md`
