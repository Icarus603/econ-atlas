## ADDED Requirements
### Requirement: Browser-backed sampling for protected sources
Sample harvesting MUST detect high-protection `source_type` values (e.g., Wiley, Oxford, ScienceDirect, Chicago, INFORMS) and use a headless Chromium session via Playwright to fetch entry pages so Cloudflare/Akamai challenges complete before HTML is captured.

#### Scenario: Protected source routes through browser
- **GIVEN** `samples collect` processes a journal whose `source_type` is in the protected allowlist
- **WHEN** it follows each entry link
- **THEN** it launches headless Chromium via Playwright, waits for the page to settle or hit a configurable timeout, and saves the rendered DOM to `samples/<source_type>/<slug>/<entry>.html`.

#### Scenario: Report browser sampling status
- **GIVEN** browser sampling runs for one or more entries
- **WHEN** the command completes
- **THEN** the summary output states how many entries succeeded or failed in browser mode so operators know if manual follow-up is required.

### Requirement: Credential/cookie injection for browser runs
Operators MUST be able to supply login credentials and/or static cookies via `.env`/environment variables that the browser sampler injects before navigation while remaining optional for sites that do not need them.

#### Scenario: Credentials provided
- **GIVEN** `.env` contains credentials or cookie strings for a protected publisher
- **WHEN** browser sampling is initialized
- **THEN** the Playwright session applies those values (login flow or cookie set) before requesting the DOI page so authenticated HTML is retrieved when required.

#### Scenario: No credentials configured
- **GIVEN** no relevant env vars exist
- **WHEN** browser sampling runs for a site that does not need authentication
- **THEN** the sampler proceeds without injection and still stores the resulting HTML.
