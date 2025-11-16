## 1. Dependencies & Setup
- [x] 1.1 Add Playwright Python dependency and document `uv run playwright install chromium` workflow (include env vars for credentials/cookies).

## 2. Browser Sampling Backend
- [x] 2.1 Implement a sampler path that detects high-protection `source_type` values and routes them through Playwright headless Chromium.
- [x] 2.2 Support injecting credentials/cookies read from `.env`/environment before navigation; no-op when data missing.
- [x] 2.3 Persist DOM to `samples/<source_type>/<slug>/<entry>.html` with success/failure annotations in the run report.

## 3. Quality Gates
- [x] 3.1 Add automated tests (unit/integration as feasible) that cover routing + post-processing logic.
- [x] 3.2 Update docs to explain the new flow, controls (timeouts, rate limits), and troubleshooting tips.
