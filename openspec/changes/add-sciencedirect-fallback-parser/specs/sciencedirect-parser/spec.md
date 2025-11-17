## ADDED Requirements
### Requirement: ScienceDirect fallback parser extracts canonical metadata
The project MUST provide a parser that consumes ScienceDirect fallback `abs` HTML (without `window.__NEXT_DATA__`) and returns normalized article metadata—title, DOI/PII, authors + affiliations, publication date, abstract text, keywords/highlights, and PDF link—using DOM selectors or meta tags.

#### Scenario: Parse fallback article preview
- **GIVEN** a saved ScienceDirect `samples/sciencedirect/<slug>/<entry>.html` file that only contains the static Article Preview DOM
- **WHEN** the parser runs with that HTML and the entry URL/PII
- **THEN** it emits a structured record populating every field that exists in the DOM (e.g., title from `<h1 data-qa="article-title">`, authors from `data-qa="author-name"`, DOI from `meta[name="citation_doi"]`, etc.), making the record ready for downstream storage without relying on Next.js JSON.

### Requirement: Parser surfaces coverage gaps and provenance
The parser MUST flag which required fields could not be extracted from fallback DOM and expose whether each field was derived from DOM text, meta tags, or heuristics, so operators can distinguish true absences from parser bugs.

#### Scenario: Missing PDF or keywords are reported
- **GIVEN** a fallback HTML lacking `data-qa="download-pdf"` or keyword chips
- **WHEN** the parser runs
- **THEN** it marks those fields as `missing` (or records the reason) in its structured output/log so the CLI and tests can surface "partial coverage" instead of silently emitting nulls.

### Requirement: CLI/automation entry point validates parser output
The CLI MUST expose a command or subcommand that runs the fallback parser against saved ScienceDirect samples, writes machine-readable JSON (or summaries), and exits non-zero if parsing fails or required fields are missing.

#### Scenario: Samples parse command audits fallback support
- **GIVEN** an operator runs `econ-atlas samples parse sciencedirect --input samples/sciencedirect --output tmp/scd.json`
- **WHEN** the command iterates over HTML files
- **THEN** it invokes the parser for each sample, writes structured results, and prints a summary of successes/missing fields, exiting non-zero if any article failed parsing so regressions are caught before crawler integration.
