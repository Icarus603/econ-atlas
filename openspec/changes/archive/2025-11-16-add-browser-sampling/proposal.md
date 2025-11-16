## Why
- Existing `samples collect` command fetches DOI/abstract pages via `httpx`, but high-protection sites (Wiley, Oxford, ScienceDirect, Chicago, INFORMS, etc.) block direct HTTP requests with Cloudflare/Akamai even with fresh cookies.
- These publishers require running JavaScript, solving human checks, or carrying complex session tokens that raw HTTP clients cannot satisfy, leaving us without DOM samples needed for parser development.

## What Changes
1. Introduce Playwright/Chromium headless sampling backend. When a journal `source_type` is in a high-protection allowlist, use the browser engine to open the DOI page, wait for defense challenges to finish, and capture the final HTML.
2. Load optional login credentials or extra cookies from `.env` entries and inject them into the headless browser before navigation. Skip auth when the site does not require it.
3. Continue writing captured HTML to `samples/<source_type>/<slug>/<entry>.html`, but annotate run reports so operators know when browser mode succeeds or fails.
4. Document Playwright setup (e.g., `uv run playwright install chromium`), runtime dependencies, and timeout/rate-limit controls.
5. Update specs/task lists so high-protection sources explicitly require headless sampling, with TODOs covering dependency install, sampler implementation, tests, and docs.

## Impact
- Enables retrieving DOM samples from previously blocked publishers, unblocking future parser work.
- Adds Playwright + Chromium dependencies, so docs must spell out environment requirements.
- Browser sessions will run longer per entry; batch/timeout controls mitigate the extra overhead.
