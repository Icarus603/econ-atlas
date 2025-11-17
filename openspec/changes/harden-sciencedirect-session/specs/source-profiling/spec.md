## ADDED Requirements
### Requirement: ScienceDirect sampling must reuse a warmed persistent browser session
ScienceDirect articles MUST be fetched with a Playwright context that reuses a user-provided Chromium profile (user data dir) and proves that `window.__NEXT_DATA__` was captured; operators need a CLI workflow to warm the session manually before automated sampling reruns.

#### Scenario: Warmup command prepares the profile
- **GIVEN** an operator runs `econ-atlas samples scd-session warmup --profile-dir /tmp/scd-profile`
- **WHEN** the command launches Chromium
- **THEN** it uses headed mode with `launch_persistent_context`, opens ScienceDirect, and after the operator completes Cloudflare/login challenges it prints instructions (including the profile path/localStorage export) so `.env` can reference the warmed profile for future runs.

#### Scenario: Sampling fails fast without a profile
- **GIVEN** `samples collect --include-source sciencedirect` runs without `SCIENCEDIRECT_USER_DATA_DIR`
- **WHEN** the collector is about to fetch ScienceDirect entries
- **THEN** it aborts that journal with a clear error directing the operator to run the warmup command instead of silently grabbing fallback HTML.

#### Scenario: JSON capture verification
- **GIVEN** the sampler saves a ScienceDirect article
- **WHEN** the resulting DOM does not include `window.__NEXT_DATA__` (or the `<pre id="browser-snapshot-data">` block)
- **THEN** the run marks that entry as failed, surfaces the debug trace/screenshot paths, and suggests re-running warmup so parser work never proceeds with blank HTML.
