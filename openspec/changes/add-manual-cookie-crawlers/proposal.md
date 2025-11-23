# Change: Separate manual cookie-based crawlers (6 journals)

## Why
- Six journals (Economic History Review, International Economic Review, Journal of Accounting Research, Journal of Political Economy, Management Science, Strategic Management Journal) still require browser + cookies, and keeping them inside the main `src/econ_atlas/` path keeps optional/manual logic mixed with the automated 33-source flow.
- Ops want a clearly isolated entrypoint that they can run on a schedule after updating cookies, without risking side effects on the automated pipeline or packaging.

## What Changes
- Introduce a `manual_crawlers/` toolkit (own entrypoint, config, and docs) dedicated to these six cookie-bound journals, writing outputs in the same JSON schema as the main pipeline.
- Provide explicit env sample + documentation for collecting and refreshing cookies, plus failure handling when cookies are missing/expired.
- Keep the main CLI and packaging unaware of these manual crawlers to avoid pulling Playwright/browser deps or cookies into the automated flow.

## Impact
- Affected specs: new capability for manual cookie-based crawl operations.
- Affected code: new `manual_crawlers/` directory (CLI/tooling, env sample, docs), no behavioral change to `src/econ_atlas/`.
