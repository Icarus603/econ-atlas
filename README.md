# econ-atlas

Automated crawler for economics/management journals listed in `list.csv`. The CLI fetches RSS feeds, stores each journal's history as JSON, and translates non-Chinese abstracts into Chinese using DeepSeek.

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

The CLI loads `.env` automatically in development. In production, supply `DEEPSEEK_API_KEY` via environment variables or your secret manager.
