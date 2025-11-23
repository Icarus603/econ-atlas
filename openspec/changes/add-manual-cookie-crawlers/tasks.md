## 1. Scaffolding
- [x] Create `manual_crawlers/` directory with README describing scope (six cookie-based publishers) and runtime expectations.
- [x] Add `manual_crawlers/.env.example` limited to required cookies/UA/browser settings for those publishers; exclude automated-source variables.

## 2. CLI/tooling
- [x] Add a standalone entrypoint (e.g., `manual_crawlers/run.py` or Typer app) to run selected manual sources with output path selection.
- [x] Ensure output JSON matches the main schema so data can live beside automated outputs.
- [x] Implement clear failure/warning messaging when cookies are missing/expired.

## 3. Packaging & isolation
- [x] Keep manual crawler dependencies/config isolated from the main package (no changes to `src/econ_atlas/` requirements or CLI).
- [x] Document how to schedule/operate the manual command (including cookie refresh cadence) without impacting the automated 33-source pipeline.

## 4. Validation
- [x] Add minimal tests or smoke checks for the manual entrypoint wiring (argument parsing + missing-cookie failure).
- [x] Run `openspec validate add-manual-cookie-crawlers --strict` and ensure it passes.
