## ADDED Requirements

### Requirement: Per-journal JSON archives
Each journal MUST persist to its own JSON file under a configurable output directory (default `data/`).

#### Scenario: Writing a new journal file
- **GIVEN** no file exists for `中国社会科学`
- **WHEN** the crawler finishes processing that journal
- **THEN** it creates `data/zhong-guo-she-hui-ke-xue.json` containing journal metadata and an `entries` array with the normalized articles.

#### Scenario: Updating an existing file
- **GIVEN** the JSON file already exists
- **WHEN** new entries are available
- **THEN** the crawler appends the new entries, updates `last_run_at`, and preserves the previous entries untouched.

### Requirement: Deduplication and incremental history
The storage layer MUST prevent duplicate entries while preserving full history of previously crawled articles.

#### Scenario: Duplicate RSS entry
- **GIVEN** an article with the same canonical `id` appears again in the feed
- **WHEN** the crawler processes it
- **THEN** storage detects the duplicate and skips inserting another copy while optionally updating metadata (e.g., translation status) if the new record is richer.

#### Scenario: New article appended
- **GIVEN** an entry with a unique `id`
- **WHEN** it is stored
- **THEN** the article is appended to the JSON file with `fetched_at` and `first_seen_at` timestamps, keeping chronological order (newest last or first, defined in implementation notes) without removing earlier entries.

### Requirement: Atomic, validated writes
Writes MUST be atomic and operate on validated data to avoid corrupting archives.

#### Scenario: Atomic persistence
- **GIVEN** entries are ready to be written
- **WHEN** the storage layer saves a file
- **THEN** it serializes JSON to a temporary file within the target directory and replaces the old file only after serialization succeeds.

#### Scenario: Schema validation
- **GIVEN** malformed data (e.g., missing `id` or `title`)
- **WHEN** validation runs before writing
- **THEN** the storage layer raises an error and does not modify existing files, allowing the CLI to report the failure.
