# Change Proposal: plan-crawler-foundation

## Summary
We need a reproducible plan for the `econ-atlas` literature-harvesting tool. The system must crawl the `list.csv` RSS sources on a schedule (default weekly, user configurable) and capture article metadata in JSON with incremental updates and DeepSeek-powered translations for non-Chinese abstracts. This proposal formalizes the scope, architecture, and tasks required to deliver a CLI-first implementation that is ready for development now while calling out later production concerns (deployment, monitoring, richer notifications).

## Why
- Automate RSS harvesting end-to-end so the team can focus on analysis instead of manual scraping.
- Preserve historical feeds and translations in structured JSON for downstream tooling.
- Provide a reference architecture for future productionization (packaging, observability).

## Problem
- There is currently no automation that reads the curated RSS list, extracts articles, translates abstracts, and stores history.
- Manual per-journal crawling is error-prone and loses prior data because there is no structured JSON archive.
- Translation quality varies when handled manually; we want a consistent DeepSeek-backed process with controllable keys via `.env`.
- Scheduling expectations (weekly default plus manual fallback) are not documented, so there is no shared understanding across contributors.

## What Changes
This change introduces three new capabilities:
1. **crawler-cli** – a Python CLI (Typer/argparse) that loads configuration from `.env` + arguments, triggers crawls once or on a repeating interval (default 7 days), and surfaces failure states early.
2. **ingestion-pipeline** – per-journal RSS ingestion that normalizes metadata, detects language, optionally invokes the DeepSeek translation API for non-Chinese abstracts, and structures article records consistently.
3. **storage-archive** – persistent JSON stores (one file per journal) with append-only semantics, deduplication keyed by feed IDs/links, and metadata to keep both original and translated abstracts.

Out of scope for this proposal (captured as future work references):
- Production deployment packaging, Docker images, or systemd/cron automation (we will note best practices but not implement them now).
- Alerting/notification channels, retries with exponential backoff, or fetching missing metadata from journal landing pages.
- UI dashboards or analytics over the harvested data.

## Assumptions
- Development runs locally with Python 3.11+, `uv` for dependency management, and `.env` holding `DEEPSEEK_API_KEY`.
- DeepSeek HTTP API is reachable; when it is not, the pipeline should leave untranslated text and record the failure cause.
- `list.csv` is the source of truth; we can extend it later but the current schema (columns: index, 期刊名称, 官网, RSS链接, 备注, etc.) is stable during this change.
- Network access to RSS feeds is permitted when the crawler executes.

## Risks / Mitigations
- **Translation quota exhaustion** – design translator abstraction with graceful fallback (store English abstract, mark translation_status) to avoid data loss.
- **RSS schema inconsistencies** – implement normalization helpers and log missing fields; keep pipeline modular so journal-specific adapters can be added later.
- **File corruption** – write JSON atomically (temp file + rename) and validate against a schema (pydantic/dataclass) before persisting.
- **Scheduling confusion** – document CLI usage and defaults clearly, ensuring manual `--once` runs do not start long-lived schedulers.

## Specs Impacted
- `crawler-cli` (ADDED)
- `ingestion-pipeline` (ADDED)
- `storage-archive` (ADDED)

## Production / Future Considerations
- Container-friendly packaging (Docker, PyInstaller) where API keys come from env vars or secrets managers, not `.env`.
- Observability hooks (structured logs, retries, status reporting).
- Advanced fetchers for journals missing summaries/authors, and a translation queue to control costs.

## References
- Source list: `list.csv`
- DeepSeek API docs (external)
- User requirements from conversation on scheduling, translation, and storage
