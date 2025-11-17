## ADDED Requirements
### Requirement: ScienceDirect sampling must persist JSON payloads
High-protection ScienceDirect entries MUST be fetched via a browser session that injects anti-bot fingerprints, normalizes URLs to `/science/article/pii/<PII>`, and captures the `window.__NEXT_DATA__` (or equivalent) JSON alongside the HTML so parser implementations can operate even when the DOM is blank.

#### Scenario: JSON snapshot saved with HTML
- **GIVEN** `samples collect` processes a ScienceDirect entry
- **WHEN** the page loads and Playwright detects `window.__NEXT_DATA__`
- **THEN** the sampler appends the serialized JSON to the saved HTML (or writes an adjacent `.json` file) and reports whether the snapshot was captured successfully.

#### Scenario: Anti-bot fingerprint applied
- **GIVEN** ScienceDirect is classified as protected
- **WHEN** the sampler launches Chromium
- **THEN** it sets `navigator.webdriver = false`, overrides language/timezone headers, and loads user-provided cookies/profile data before requesting the page so Cloudflare/Akamai challenges are minimized.

### Requirement: ScienceDirect fallback ingestion path
Operators MUST have a documented fallback to ingest ScienceDirect HTML/JSON that was captured manually (e.g., via HAR/cURL) and to export debug artifacts when automated sampling fails.

#### Scenario: Manual sample import
- **GIVEN** an operator downloads a ScienceDirect article HTML/JSON from their own browser
- **WHEN** they run `samples collect --import-file ...` (or similar)
- **THEN** the CLI stores the payload under `samples/sciencedirect/<slug>/` following the same naming convention, so parser regression suites can consume it even if automated Playwright runs fail.

#### Scenario: Debug logs produced
- **GIVEN** an automated ScienceDirect fetch hits repeated 403/timeouts
- **WHEN** the operator passes `--sdir-debug`
- **THEN** the CLI emits HTTP status, challenge identifiers, and optionally a screenshot/network HAR so engineers can adjust cookies or fingerprint settings.
