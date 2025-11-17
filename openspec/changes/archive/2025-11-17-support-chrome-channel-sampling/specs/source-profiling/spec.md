## MODIFIED Requirements
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
