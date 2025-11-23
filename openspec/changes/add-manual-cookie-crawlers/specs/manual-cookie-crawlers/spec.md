## ADDED Requirements

### Requirement: Manual crawlers live outside the main package
The project SHALL host cookie-dependent crawlers for six journals (Economic History Review, International Economic Review, Journal of Accounting Research, Journal of Political Economy, Management Science, Strategic Management Journal) in a separate `manual_crawlers/` toolkit, not under `src/econ_atlas/`, so the automated 33-source pipeline and packaging remain untouched by browser/cookie dependencies.

#### Scenario: Manual entrypoint is isolated
- **GIVEN** an operator runs the manual command from `manual_crawlers/` (e.g., `python run.py --sources oxford,wiley`)
- **WHEN** the command executes
- **THEN** it does not import or modify the main `econ_atlas` CLI/modules, and the main package can still be installed/run without the manual crawler dependencies.

### Requirement: Manual command enforces cookie prerequisites
The manual crawler command SHALL require per-source cookie/session configuration for these six journals (env file provided in `manual_crawlers/.env.example`) and fail fast with an actionable error when the needed values are missing or clearly expired.

#### Scenario: Missing cookie blocks run
- **GIVEN** an operator invokes the manual command without `OXFORD_COOKIES` set
- **WHEN** `--sources oxford` is requested
- **THEN** the command exits non-zero with a clear message that cookies are required and where to paste them (Network tab request headers), without attempting the crawl.

### Requirement: Output compatibility with automated data
The manual crawlers SHALL write results using the same JSON schema and directory structure as the automated pipeline, allowing the six sources to co-exist in `data/` without post-processing.

#### Scenario: Save alongside automated outputs
- **GIVEN** the manual command runs for `--sources oxford` with `--output-dir ../data`
- **WHEN** it completes successfully
- **THEN** it writes/updates `../data/<journal-slug>.json` using the existing article schema so downstream tooling can consume it identically to automated journals.

### Requirement: Operator-focused scheduling support
The manual command SHALL support selecting which of the six sources to run and surface cron-friendly status (summary and non-zero exit on any failure) so ops can schedule periodic runs after refreshing cookies.

#### Scenario: Subset run with clear status
- **GIVEN** an operator runs `python run.py --sources oxford,chicago`
- **WHEN** one source succeeds and one fails due to 401/403
- **THEN** the command prints per-source success/failure and exits non-zero so cron/systemd can alert on the failure.
