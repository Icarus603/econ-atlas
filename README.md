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

When targeting ScienceDirect you can enable diagnostics:

```bash
uv run econ-atlas samples collect --include-source sciencedirect --limit 1 --sdir-debug
```

This writes screenshots + metadata to `samples/_debug_sciencedirect/`, making it easier to inspect Cloudflare challenges.

You can also import manually captured files (e.g., DOM/JSON saved from Chrome):

```bash
uv run econ-atlas samples import sciencedirect journal-slug ~/Downloads/article.html --entry-id manual-snapshot
```

The imported file is copied to `samples/sciencedirect/<journal-slug>/manual-snapshot.html` so parser regressions can use it.

Summarize which publishers/slugs already have HTML on disk:

```bash
uv run econ-atlas samples inventory --pretty
```

The inventory command emits JSON (or `--format csv`) containing per-`source_type` sample counts, most recent timestamps, and manual notes for blocked feeds. Use it alongside the parser dossiers stored in `docs/parser_profiles/<source_type>.md`, which document selectors, required cookies, and outstanding TODOs for each publisher.

Protected sources (Wiley, Oxford, ScienceDirect, Chicago, INFORMS) require a headless Chromium session via Playwright to bypass Cloudflare/Akamai challenges. Install the browser runtime once:
```bash
uv run playwright install chromium
```
Optionally provide cookies or HTTP credentials via `.env` using `WILEY_COOKIES`, `OXFORD_COOKIES`, etc., and `*_BROWSER_USERNAME`/`*_BROWSER_PASSWORD` pairs. If Cloudflare 仍要求特定 UA/header，可再设置 `WILEY_BROWSER_USER_AGENT` 以及 `WILEY_BROWSER_HEADERS`（JSON 字符串，键为 header 名，值为具体字符串；包含 `sec-ch-ua`、`Accept-Language`、`sec-fetch-*` 等），浏览器采样器会在打开页面前一并注入。这些值让 Playwright 与真实浏览器完全一致，CLI 结束时也会报告浏览器模式的成功/失败统计。

For ScienceDirect we additionally support:
- `SCIENCEDIRECT_USER_DATA_DIR`: point to a Chrome/Chromium profile captured from your desktop session so Playwright inherits stored cookies/CF tokens.
- `SCIENCEDIRECT_BROWSER_INIT_SCRIPT`: inline JS (or path to a `.js` file) executed via `context.add_init_script` to spoof browser fingerprints (`navigator.webdriver`, `chrome.runtime`, etc.).
- `SCIENCEDIRECT_BROWSER_LOCAL_STORAGE`: JSON object written into `localStorage` before navigation (e.g., `{ "OptanonConsent": "..." }`).
- `SCIENCEDIRECT_BROWSER_HEADLESS`: set to `false` to launch Chromium in headed mode when debugging Cloudflare challenges; default is `true`.

The sampler also dumps `window.__NEXT_DATA__` into `<pre id="browser-snapshot-data">` so parser code can consume a structured payload even if the DOM stays blank.

> ⚠️ Chicago/INFORMS RSS feeds remain guarded by Cloudflare. Even with Playwright and copied article cookies, responses may still return the “Just a moment…” HTML instead of XML, so no samples are saved. To unblock these sources you must capture cookies from a successful RSS visit (not just article pages) or use an alternate feed/API.

The CLI loads `.env` automatically in development. In production, supply `DEEPSEEK_API_KEY` via environment variables or your secret manager.

## Output
- Each journal produces a JSON file `data/<journal-slug>.json` containing journal metadata, historical entries, translations, and fetch timestamps.
- Files are written atomically and can be version-controlled or ingested by other tooling (e.g., dashboards, search indices).

## Roadmap (High-Level)
1. Harden crawlers for feeds missing abstracts/authors by scraping article pages when necessary.
2. Add observability (structured logs, alerts, retry policies) suitable for cron/system services.
3. Package the CLI for easy distribution (pipx, Docker) and support additional translation providers or offline models.
