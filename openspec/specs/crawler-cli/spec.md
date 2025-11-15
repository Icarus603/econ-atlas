# crawler-cli Specification

## Purpose
TBD - created by archiving change plan-crawler-foundation. Update Purpose after archive.
## Requirements
### Requirement: CLI runs manual or scheduled crawls
The `econ-atlas` CLI MUST support both one-off executions and repeating schedules with a weekly default.

#### Scenario: Manual crawl (fallback mode)
- **GIVEN** a developer runs `econ-atlas crawl --once`
- **WHEN** the command starts
- **THEN** it loads configuration, runs the ingestion pipeline exactly once across every RSS source, writes JSON outputs, prints a per-journal summary, and exits with code `0` on success or non-zero on failure.

#### Scenario: Scheduled crawl (default weekly)
- **GIVEN** a developer runs `econ-atlas crawl` without `--once`
- **WHEN** no interval override is provided
- **THEN** the CLI keeps the process alive and re-runs the ingestion pipeline every 7 days until interrupted.

#### Scenario: Custom cadence
- **GIVEN** the user specifies `--interval "2d"` (or `--interval-seconds 172800`)
- **WHEN** the CLI runs
- **THEN** it schedules the crawl job at the requested cadence while preserving manual cancellation controls (Ctrl+C to stop).

### Requirement: Config + secrets handling
The CLI MUST read `.env` files during development, fall back to environment variables in other environments, and safely handle missing DeepSeek API keys.

#### Scenario: .env present
- **GIVEN** a `.env` contains `DEEPSEEK_API_KEY=secret`
- **WHEN** `econ-atlas crawl` starts
- **THEN** the CLI loads the variable before initializing translators so API calls succeed without extra flags.

#### Scenario: Missing API key
- **GIVEN** no DeepSeek key is found in `.env` or the environment
- **WHEN** translation is required
- **THEN** the CLI aborts before contacting feeds, prints a clear error suggesting how to set the variable, and returns a non-zero exit code.

### Requirement: Operator controls and surfacing
Operators MUST be able to point the CLI at alternate input/output paths and see a concise summary of what happened.

#### Scenario: Alternate paths
- **GIVEN** the user passes `--list-path /tmp/list.csv --output-dir data/custom`
- **WHEN** the crawl runs
- **THEN** the CLI reads that CSV and writes JSON files into the custom directory without touching defaults.

#### Scenario: Execution summary
- **GIVEN** a crawl completes (manual or scheduled run tick)
- **WHEN** the CLI finalizes the tick
- **THEN** it prints structured counts (journals processed, new articles, translations attempted/failed) so operators can monitor runs without digging into JSON.

