## ADDED Requirements
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
