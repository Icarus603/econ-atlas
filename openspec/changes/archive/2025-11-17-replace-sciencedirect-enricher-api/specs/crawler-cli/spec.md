## MODIFIED Requirements
### Requirement: CLI runs manual or scheduled crawls
The `econ-atlas` CLI MUST support both one-off executions and repeating schedules while choosing the appropriate enrichment strategy for each source.

#### Scenario: ScienceDirect enrichment via API
- **GIVEN** an operator configures `ELSEVIER_API_KEY` (and any required identifiers) in the environment
- **WHEN** `econ-atlas crawl` processes ScienceDirect journals
- **THEN** the crawler uses the Elsevier API to fetch structured article metadata instead of launching Playwright, while falling back to the legacy DOM parser only when the API is unavailable, logging the reason without stopping the run.

### Requirement: Config + secrets handling
The CLI MUST read `.env` / environment variables, validate required secrets, and surface actionable warnings when optional integrations (e.g., Elsevier API) are missing.

#### Scenario: Missing Elsevier API key warns but does not block
- **GIVEN** no `ELSEVIER_API_KEY` is present
- **WHEN** `econ-atlas crawl` starts
- **THEN** the CLI prints a warning that ScienceDirect will use the degraded fallback path, but the run proceeds so other journals are unaffected.
