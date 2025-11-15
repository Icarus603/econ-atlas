# Design: plan-crawler-foundation

## Architecture Overview
We will ship a small-but-extensible Python package under `src/econ_atlas/` with these modules:

| Module | Responsibility |
| --- | --- |
| `config.py` | Load `.env`, CLI options, and defaults (list path, output dir, schedule). Validates that `DEEPSEEK_API_KEY` exists when translation is enabled. |
| `cli.py` | Typer-based CLI exposing `crawl` command plus flags for manual vs scheduled runs. Delegates to `runner.py`. |
| `sources/list_loader.py` | Reads `list.csv`, maps column headers to `Journal` dataclasses (name, rss_url, language_hint, notes). Skips rows without RSS links. |
| `ingest/feed.py` | Wraps `feedparser` to fetch RSS URLs, normalize heterogenous fields (title, summary, authors, published, link, guid). |
| `translate/deepseek.py` | Implements `Translator` protocol via DeepSeek REST API using the key from env vars; handles batching per abstract, language detection (via `langdetect`), and structured errors. |
| `storage/json_store.py` | Maintains `data/<slug>.json` including journal metadata, `entries` array, and `last_run_at`. Handles deduplication + atomic writes. |
| `runner.py` | Coordinates list loading, ingestion per journal, translation, and persistence; returns status per journal for CLI reporting. |
| `schedule/loop.py` (optional) | Provides a simple asyncio loop / APScheduler job that re-invokes `runner` every configured interval (default 7 days). |

The package will default to synchronous execution to keep dependencies light. We can switch to async fetch later by swapping `feedparser` for `httpx` + `aiofeedparser`.

## DeepSeek Translation Flow
1. Detect language for each article abstract (fallback to feed metadata or journal language hint).
2. If language is detected as Chinese (`zh`), store the original abstract in both `abstract_original` and `abstract_zh` (no API call).
3. Otherwise, call DeepSeek completion/translation endpoint with a deterministic prompt instructing the model to output fluent Simplified Chinese. Record response text plus metadata (`translator: "deepseek"`, `translated_at`, `status`).
4. On API failure or missing key, record `translation_status="failed"` and keep the original text for future retries.

The translator module will expose a `translate(text, source_lang, target_lang="zh") -> TranslationResult` to allow future providers (e.g., offline models) without rewriting ingestion.

## Scheduling Strategy
- Default behavior: `econ-atlas crawl --once` executes immediately and exits (manual fallback).
- Automated behavior: `econ-atlas crawl --interval 7d` (default) keeps the process alive, calling the runner at the requested cadence using a lightweight scheduler loop (either APScheduler or a custom `while True: run; sleep(interval)` to avoid extra dependencies). We will start with a simple asyncio loop to honor the “minimal first” guardrail.
- The CLI prints instructions about how to integrate with cron/systemd for production deployments but does not attempt to install timers.

## Data & Storage Model
Each journal file (`data/<journal_slug>.json`) will contain:
```json
{
  "journal": {
    "name": "...",
    "rss_url": "...",
    "notes": "...",
    "last_run_at": "ISO-8601"
  },
  "entries": [
    {
      "id": "guid-or-link",
      "title": "...",
      "authors": ["..."],
      "link": "...",
      "published_at": "ISO-8601",
      "abstract_original": "...",
      "abstract_language": "en",
      "abstract_zh": "...",
      "translation": {
        "status": "success|skipped|failed",
        "translator": "deepseek",
        "translated_at": "ISO-8601",
        "error": null
      },
      "fetched_at": "ISO-8601",
      "source": "RSS"
    }
  ]
}
```
Deduplication occurs by `id` (feed `id` if present, else normalized `link`, else `sha256(title+link)`). When an entry already exists, we skip writing duplicates but may upgrade missing fields (e.g., translation) by merging in-place before saving.

Atomic writes: compose the JSON structure in memory, dump to a temp file inside the same directory, and `os.replace` it over the previous file.

## Future / Production Notes
- Package/executable distribution (pipx, Docker, PyInstaller) should rely on environment variables instead of `.env`.
- Observability: structured logging, metrics, retries, failure notifications (email/chat) to be added later.
- Deeper crawlers for sources lacking abstracts/authors, plus queue-based translation to reduce API costs, remain open follow-ups.
