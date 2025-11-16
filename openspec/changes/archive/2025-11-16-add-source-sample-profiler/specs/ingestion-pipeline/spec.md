## MODIFIED Requirements
### Requirement: Journal source loading
The ingestion pipeline MUST treat `list.csv` as the single source of truth for journals, deriving only the name + RSS link columns **and a `source_type` classification that advertises the upstream provider/publisher**.

#### Scenario: Source type classification
- **GIVEN** a CSV row includes a `source_type` value (e.g., `cnki`, `wiley`, `cambridge`, `chicago`, `elsevier`)
- **WHEN** sources are loaded
- **THEN** the loader emits the normalized slug along with that `source_type`, and rejects/flags rows whose value is missing or outside the supported list so downstream tooling can pick the right scraping strategy.
