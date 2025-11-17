# source-profiling Specification

## Purpose
TBD - created by archiving change add-source-sample-profiler. Update Purpose after archive.
## Requirements
### Requirement: Sample HTML harvesting
The tooling MUST provide a command or script that reads `list.csv`, filters for journals whose `source_type` is in a configured include-set, pulls the latest N RSS entries per journal, follows the entry `link`, and saves the resulting HTML into `samples/<source_type>/<slug>/<entry_id>.html` (creating directories as needed).

#### Scenario: Limited samples per journal
- **GIVEN** an operator runs the sample harvester with `--limit 3`
- **WHEN** it processes a journal with a valid RSS feed
- **THEN** it downloads at most 3 unique article HTML files for that journal, naming them deterministically from the entry id or slug so later runs can overwrite/update the same files.

### Requirement: Sample harvest reporting
Operators MUST be able to see which journals succeeded or failed during sample collection.

#### Scenario: Summary output
- **GIVEN** the sample harvester runs across multiple journals
- **WHEN** it finishes
- **THEN** it prints a summary table (journals attempted, HTML files saved, failures with reasons) and exits non-zero if any journal failed so operators know to retry or investigate.

### Requirement: Browser-backed sampling for protected sources
Operators MUST be able to force protected-source sampling to launch Playwright with a user-specified Chrome build (channel or executable path) so warmed profiles and trusted TLS fingerprints can be reused whenever default Chromium is blocked.

#### Scenario: Launch with user-specified Chrome build
- **GIVEN** `.env` supplies `SCIENCEDIRECT_BROWSER_CHANNEL=chrome` or `SCIENCEDIRECT_BROWSER_EXECUTABLE=/Applications/Google Chrome.app/...`
- **WHEN** `samples collect --include-source sciencedirect` launches its Playwright browser
- **THEN** it uses the provided channel/executable (falling back to default Chromium when unset) so operators can reuse their trusted Chrome profile and TLS fingerprint during sampling.

#### Scenario: Invalid launch options are rejected
- **GIVEN** both `*_BROWSER_CHANNEL` and `*_BROWSER_EXECUTABLE` are set for the same source
- **WHEN** browser sampling is initialized
- **THEN** the command fails fast with a descriptive error telling the operator to choose exactly one option before retrying, preventing Playwright from receiving conflicting launch arguments.

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

### Requirement: DOM profiling documentation
For every `source_type` that has HTML samples checked into `samples/`, the project MUST maintain a Markdown dossier under `docs/parser_profiles/<source_type>.md` describing how to extract required article fields (title, authors, affiliations, DOI, publication date, abstract, keywords/JEL, PDF link) from that publisher's DOM.

#### Scenario: Document selectors and prerequisites
- **GIVEN** `samples/wiley/<slug>/<entry>.html` exists
- **WHEN** the DOM profiling doc is created/updated
- **THEN** it lists the sample file(s) used, the CSS/XPath selectors (or JS hooks) for each required field, and any prerequisites such as login cookies, proxy domains, or "click to expand" interactions that a parser implementation must reproduce.

#### Scenario: Include protected/legacy sources
- **GIVEN** a protected publisher like Chicago or INFORMS where RSS/entry access needs special cookies or headers
- **WHEN** its DOM profiling doc is produced
- **THEN** the document explains how to acquire the needed session (RSS cookies vs. article cookies) so future sampling + parsing can be repeated.

### Requirement: Parser coverage tracking
The project MUST provide an automated check that ensures every `source_type` present under `samples/` has a corresponding DOM profiling doc and that each doc declares coverage for the mandatory fields.

#### Scenario: Coverage script flags gaps
- **GIVEN** a new `source_type` directory is added under `samples/` without `docs/parser_profiles/<source_type>.md`
- **WHEN** the coverage check runs (CI or local command)
- **THEN** it fails with a clear message identifying the missing doc so maintainers update the profiling notes before merging parser work.

#### Scenario: Field completeness validation
- **GIVEN** a profiling doc exists but omits selectors for required fields (e.g., PDF link missing)
- **WHEN** the coverage check parses the doc/metadata
- **THEN** it reports which fields are incomplete so developers can't declare the source "parser-ready" until documentation is complete.

