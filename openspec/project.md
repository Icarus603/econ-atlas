# Project Context

## Purpose
Automate collection of economics/management journal publications from RSS feeds, translate non-Chinese abstracts into Chinese, and persist the results for downstream analysis.

## Tech Stack
- Python 3.11+
- uv for dependency + virtual environment management
- Typer CLI, feedparser, requests/httpx, langdetect, python-dotenv, APScheduler (optional)

## Project Conventions

### Code Style
- Follow Ruff + Black defaults (via `uv run ruff check . --fix`).
- All public functions/classes documented with docstrings and type hints (mypy strict).
- Avoid print debugging in shipped code; use logging.

### Architecture Patterns
- Modular packages under `src/econ_atlas/` (config, CLI, ingestion, translation, storage).
- Functional-core / imperative-shell: CLI orchestrates small, testable services.
- Spec-driven development via OpenSpec (proposal → implementation → archive).

### Testing Strategy
- Unit tests for translators, storage, and parsers.
- Integration smoke tests for CLI pipelines where practical (network mocked).
- Commands: `uv run ruff check . --fix`, `uv run mypy .`, `uv run pytest -q`.

### Git Workflow
- Default branch `main`.
- Feature work occurs on topic branches; merge via PR.
- Conventional commit prefixes encouraged but not enforced; keep messages descriptive.

## Domain Context
- `list.csv` enumerates economics/management journals with RSS feeds (Chinese + international).
- Output must preserve historical entries per journal and translate non-Chinese abstracts into Chinese.

## Important Constraints
- Offline-friendly: core pipeline must run locally without cloud infrastructure.
- DeepSeek API key managed via `.env` during development; production should use env vars or secret managers.
- No GUI requirements; CLI + JSON outputs only for now.

## External Dependencies
- DeepSeek API for translation.
- Various journal RSS feeds (CNKI, ScienceDirect, Wiley, Cambridge, etc.).
