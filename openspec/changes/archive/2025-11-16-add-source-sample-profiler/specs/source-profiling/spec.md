## ADDED Requirements
### Requirement: Sample HTML harvesting
The tooling MUST provide a command or script that reads `list.csv`, filters for journals whose `source_type` is in a configured include-set, pulls the latest N RSS entries per journal, follows the entry `link`, and saves the resulting HTML into `samples/<source_type>/<slug>/<entry_id>.html` (creating directories as needed).

#### Scenario: Limited samples per journal
- **GIVEN** an operator runs the sample harvester with `--limit 3`
- **WHEN** it processes a journal with a valid RSS feed
- **THEN** it downloads at most 3 unique article HTML files for that journal, naming them deterministically from the entry id or slug so later runs can overwrite/update the same files.

### Requirement: Sample harvest reporting
Operators MUST be able to see which journals succeeded or failed during sample collection.

#### Scenario: Summary output
- **GIVEN** the sample harvester runs across multiple journals
- **WHEN** it finishes
- **THEN** it prints a summary table (journals attempted, HTML files saved, failures with reasons) and exits non-zero if any journal failed so operators know to retry or investigate.
