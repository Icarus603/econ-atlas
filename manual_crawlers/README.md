# Manual Cookie-Based Crawlers

This toolkit is for the six journals that still require browser + cookies and should not run in the automated 33-source pipeline:

- Economic History Review (Wiley)
- International Economic Review (Wiley)
- Journal of Accounting Research (Wiley)
- Journal of Political Economy (Chicago)
- Management Science (INFORMS)
- Strategic Management Journal (Wiley)

## How to run

1) Prepare cookies for the sources you intend to run (see below).  
2) Create a `.env` in this directory based on `.env.example`.  
3) Run:
```bash
uv run python manual_crawlers/run.py --sources oxford,wiley --output-dir ../data
```

The command exits non-zero when a requested source is missing cookies or fails, which is cron-friendly for alerts.

### Scheduling example (cron)

```cron
# refresh cookies before running; cron will alert if exit code != 0
0 3 * * 1 cd /path/to/econ-atlas && uv run python manual_crawlers/run.py --sources economic-history-review,international-economic-review,strategic-management-journal --output-dir ./data >> manual_crawlers/manual.log 2>&1
```

## Getting cookies

Use a logged-in browser session, open an article page for the publisher, then:
- Open DevTools → Network, filter by the article request, and copy the full `cookie` header.
- Paste the value into the matching env var (e.g., `OXFORD_COOKIES=`) in `.env`.

Refresh cookies periodically; expect them to expire.

## Outputs

Results are written to the same JSON schema/path as the automated pipeline (journal slug files under `data/`). The crawling logic lives here and stays separate from `src/econ_atlas/`.

## Isolation from the automated pipeline

- No imports from `src/econ_atlas/`; dependencies stay local to this toolkit.
- `.env.example` here only lists the cookie variables needed for these six journals.
- Packaging/runs of the main `econ-atlas` CLI remain unchanged.
