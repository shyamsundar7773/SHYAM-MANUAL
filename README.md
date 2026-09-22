# SHYAM MANUAL

SHYAM MANUAL is a Streamlit-based job interview command center covering Candidate Profile, Job Radar, Job Intelligence, Resume Studio, Applications, SQL Technical Notes, Technical Round, Project & Practical, Non-Technical, Live Interview, Evaluation, 20-Day Mission, and Progress.

## Setup

Use Python 3.10+:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
```

## Run

The database is initialized automatically on startup. To initialize it explicitly:

```powershell
py -c "from config.settings import get_settings; from data.database import initialize_database; initialize_database(get_settings().database_path)"
py -m streamlit run app.py
```

## Configuration

Copy `.env.example` to `.env`. On startup, the application loads supported `KEY=VALUE` entries from that file without overriding variables already supplied by the process environment. Supported variables are `AI_PROVIDER`, `AI_API_KEY`, `AI_MODEL`, and `DATABASE_PATH`. API keys are never hard-coded or displayed.

## Tests

```powershell
py -m pytest -q
py -m compileall .
```

## Architecture

`app.py` is the thin Streamlit entry point. `config/` contains environment-backed settings, `data/` contains the SQLite schema, safe additive migration, idempotent seed content, connection, and repositories, `services/` contains the existing AI and job boundaries, and `ui/` contains the Streamlit pages. `tests/` exercises initialization, seeded relationships, repository CRUD/search/tag behavior, configuration, and service behavior.

## Delivered scope (Phase 0 + Phase 1 + Phase 2 + Phase 3 + Phase 4 + Phase 5 + Phase 6)

Implemented: SQLite schema and seed categories, additive `questions.personal_answer` migration, idempotent HR Screening and Non-Technical + Live Interview modules/topics/questions, repository CRUD/search/filter/count/recent APIs (including personal-answer and follow-up search), normalized question tags, command-center metrics/recent content, category/module/topic browsing, question forms with personal answers, answer reveal, browser-compatible copy controls, settings, future-ready jobs/progress/history tables, safe mock AI service, normalized job model boundary, reusable UI primitives, error handling, and tests. Phase 2 starter content covers the specified HR and Non-Technical structures and uses placeholders and guidance rather than invented personal facts.

Phase 3 adds exactly 18 SQL Technical Notes modules with representative topics, idempotent MySQL 8-baseline notes, syntax examples, memory tricks, follow-ups, and starter technical questions. Phase 4 adds the same explicit broad SQL curriculum to Technical Round with varied, tagged questions and interview metadata (expectations, reasoning, solutions, alternatives, traps, style, and source). Phase 5 adds ten database-driven Project & Practical modules with realistic topics, reusable explanation templates, clearly labeled examples/practice scenarios, and a substantial varied question bank. Project practice sets support Project Explanation, SQL Practical, Business Scenario, Data Quality, Mixed Project, Difficulty, and Follow-up filters through the shared repository and content engine. Metadata has additive migration, CRUD/search/filter support, deterministic practice-set APIs, and recorded practice history. The Technical Round and Project & Practical UIs provide module/topic navigation, practice controls, metadata-aware cards, and the existing copy/edit/delete/form workflow. The SQL route renders the learning manual before reusable question cards, while HR and Non-Technical remain generic database-driven routes.

The existing AI architecture currently uses a safe deterministic/mock fallback; no real external AI provider is configured or implemented. External job connectors are not currently configured, and application submission is never performed automatically. Seeded examples and scenarios are templates only and never assert user facts.

Phase 6 adds one editable, user-supplied candidate profile; normalized manually entered jobs with source/application URLs, remote type and structured requirements; saved jobs; application statuses/history; deterministic safe mock analysis with explicit/unverified separation; persisted match records; master resume drafts and preparation-gap mapping to existing topics. Job providers return an empty state until configured, submissions remain manual, and no candidate qualifications are invented.
