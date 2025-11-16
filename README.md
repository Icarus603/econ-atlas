<h1 align="center">econ-atlas</h1>

<p align="center">
  Automated economics-literature harvesting · DeepSeek-powered translations · JSON archives
</p>

<p align="center">
  <a href="./README_CN.md">查看中文说明</a>
</p>

---

econ-atlas is an automation project that keeps track of economics and management journals listed in `list.csv`. A Python CLI reads each RSS feed, normalizes article metadata, translates non-Chinese abstracts into Simplified Chinese via the DeepSeek API, and stores the results as per-journal JSON archives for downstream analysis.

## Purpose
- **Automated harvesting**: remove manual scraping overhead by crawling all configured RSS sources on a configurable cadence (default weekly).
- **Bilingual abstracts**: keep the original abstract plus an automatically translated Chinese version so Chinese-focused reviews can reference international literature.
- **Historical archive**: maintain append-only JSON files for each journal to preserve previously seen papers and downstream reproducibility.

## Current Status
- ✅ CLI scaffolding finished (`uv run econ-atlas crawl`). Supports one-off runs (`--once`) and simple scheduling loops.
- ✅ Source ingestion and translation pipeline implemented with DeepSeek-based translations and language detection fallbacks.
- ✅ Storage layer writes per-journal JSON files to `data/`, deduplicates feed entries, and preserves translation metadata.
- 🚧 Future work (not yet implemented): richer alerting/monitoring, missing-abstract scrapers, packaging for deployment, and production-ready scheduling integrations (cron/systemd).

## Repository Layout
- `list.csv`: source-of-truth table with journal names, RSS URLs, and `source_type` classifications (e.g., `cnki`, `wiley`, `sciencedirect`).
- `src/econ_atlas/`: Python package containing the CLI, configuration, ingestion, translation, and storage modules.
- `samples/`: HTML snapshots captured by the source-profiling utility (ignored by git).
- `openspec/`: OpenSpec proposals/specs that document requirements and future changes.
- `tests/`: unit tests for configuration, CSV loading, and storage behavior.

## Getting Started

1. Install dependencies with [uv](https://github.com/astral-sh/uv):
   ```bash
   uv sync
   ```
2. Copy `.env.example` to `.env` and add your DeepSeek API key:
   ```bash
   cp .env.example .env
   echo "DEEPSEEK_API_KEY=sk-..." >> .env
   ```
3. Run lint, type checks, and tests:
   ```bash
   uv run ruff check . --fix
   uv run mypy .
   uv run pytest -q
   ```

## CLI Usage

Run a single crawl (fallback/manual):
```bash
uv run econ-atlas crawl --once
```

Continuous schedule (default every 7 days):
```bash
uv run econ-atlas crawl
```

Key options:
- `--list-path PATH` – override the RSS CSV (defaults to `list.csv`)
- `--output-dir PATH` – directory for per-journal JSON files (defaults to `data/`)
- `--interval 12h` or `--interval-seconds 43200` – custom cadence for scheduled runs
- `--verbose/-v` – verbose logging

Collect HTML samples for non-Chinese journals to inform parser development:
```bash
uv run econ-atlas samples collect --limit 3 --include-source wiley --include-source oxford
```
This command reads `list.csv`, filters by `source_type`, fetches RSS entries, and saves each article's HTML to `samples/<source_type>/<journal-slug>/`.

Protected sources (Wiley, Oxford, ScienceDirect, Chicago, INFORMS) require a headless Chromium session via Playwright to bypass Cloudflare/Akamai challenges. Install the browser runtime once:
```bash
uv run playwright install chromium
```
Optionally provide cookies or HTTP credentials via `.env` using `WILEY_COOKIES`, `OXFORD_COOKIES`, etc., and `*_BROWSER_USERNAME`/`*_BROWSER_PASSWORD` pairs. The browser sampler injects these before navigation and the CLI summary reports browser-mode successes/failures.

> ⚠️ Chicago/INFORMS RSS feeds remain guarded by Cloudflare. Even with Playwright and copied article cookies, responses may still return the “Just a moment…” HTML instead of XML, so no samples are saved. To unblock these sources you must capture cookies from a successful RSS visit (not just article pages) or use an alternate feed/API.

The CLI loads `.env` automatically in development. In production, supply `DEEPSEEK_API_KEY` via environment variables or your secret manager.

## Output
- Each journal produces a JSON file `data/<journal-slug>.json` containing journal metadata, historical entries, translations, and fetch timestamps.
- Files are written atomically and can be version-controlled or ingested by other tooling (e.g., dashboards, search indices).

## Roadmap (High-Level)
1. Harden crawlers for feeds missing abstracts/authors by scraping article pages when necessary.
2. Add observability (structured logs, alerts, retry policies) suitable for cron/system services.
3. Package the CLI for easy distribution (pipx, Docker) and support additional translation providers or offline models.
