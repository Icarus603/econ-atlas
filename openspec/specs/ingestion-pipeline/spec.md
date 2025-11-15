# ingestion-pipeline Specification

## Purpose
TBD - created by archiving change plan-crawler-foundation. Update Purpose after archive.
## Requirements
### Requirement: Journal source loading
The ingestion pipeline MUST treat `list.csv` as the single source of truth for journals, deriving only the name + RSS link columns.

#### Scenario: CSV row with RSS
- **GIVEN** a row contains `期刊名称` and a non-empty `RSS链接`
- **WHEN** the pipeline loads sources
- **THEN** it emits a `Journal` object with `name`, `rss_url`, `slug` (normalized ASCII), and optional `notes` (from the `备注` column) ready for crawling.

#### Scenario: CSV row without RSS
- **GIVEN** a row lacks an RSS link
- **WHEN** sources are loaded
- **THEN** the row is skipped and a warning is logged so operators know the journal requires manual intervention.

### Requirement: RSS normalization
The pipeline MUST fetch every configured RSS feed and normalize entries into a consistent schema (title, summary, authors, link, published timestamp, id).

#### Scenario: Feed entry missing GUID
- **GIVEN** an RSS entry lacks `id/guid`
- **WHEN** it is normalized
- **THEN** the pipeline uses the entry URL as its canonical `id`, ensuring downstream storage can deduplicate.

#### Scenario: Authors field variations
- **GIVEN** an RSS entry encodes authors as a string or array (depending on publisher)
- **WHEN** normalization runs
- **THEN** the pipeline outputs `authors` as a list of strings, splitting comma/semicolon-separated strings if necessary.

### Requirement: Language detection and translation
The pipeline MUST store original abstracts and translate non-Chinese summaries into Chinese via DeepSeek.

#### Scenario: Chinese abstract (no translation)
- **GIVEN** language detection reports `zh` or the journal is flagged as Chinese
- **WHEN** the abstract is processed
- **THEN** the pipeline stores the original text in both `abstract_original` and `abstract_zh`, marks translation as `skipped`, and makes no API call.

#### Scenario: Non-Chinese abstract
- **GIVEN** an entry summary is detected as English (or other non-zh)
- **WHEN** the translator runs
- **THEN** it calls DeepSeek with the configured API key, stores the returned Chinese text in `abstract_zh`, records metadata (`translator`, `translated_at`, `status=success`), and retains the original text unchanged.

#### Scenario: Translation failure
- **GIVEN** DeepSeek returns an error or the API key is invalid
- **WHEN** translation is attempted
- **THEN** the pipeline logs the error, stores `translation.status="failed"` with the failure reason, and keeps the untranslated abstract for future retries.

