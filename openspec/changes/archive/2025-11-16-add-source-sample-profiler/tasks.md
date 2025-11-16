# Tasks
- [x] Update `JournalSource` metadata loading to accept a `source_type` column in `list.csv`, validate allowed values, and expose it throughout the pipeline.
- [x] Add specs for publisher classification and sample capture under the new `source-profiling` capability; outline how journals map to providers and how many samples to fetch per run.
- [x] Implement a CLI utility (or script) that reads the list, filters for configured provider types, fetches the latest N RSS entries per journal, and downloads their article HTML into `samples/<source_type>/<slug>/` while summarizing successes/failures.
- [x] Add regression tests / fixtures ensuring the loader enforces `source_type`, plus basic smoke coverage for the sample-harvest utility (mocking network where needed).
- [x] Document usage in README or dedicated docs and ensure `openspec validate add-source-sample-profiler --strict` passes.
