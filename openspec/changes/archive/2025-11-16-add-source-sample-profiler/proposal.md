# Proposal: add-source-sample-profiler

## Why
- Several English journals (e.g., Wiley, Cambridge) provide RSS feeds without real abstracts, so we must inspect their article HTML to design provider-specific scrapers.
- Operators currently have no structured way to collect these HTML samples; doing it manually with browsers is slow and error-prone.
- The ingestion pipeline also treats every journal identically because `list.csv` only records name + RSS. We need metadata that reveals the publisher/source so we can target the right parsing strategy.

## What Changes
1. Extend the journal metadata schema so `list.csv` carries a `source_type` (e.g., `cnki`, `wiley`, `cambridge`, `chicago`, `elsevier`). `JournalListLoader` must emit this attribute so downstream tooling knows which strategy applies.
2. Introduce a CLI/utility that iterates over every non-CN journal, walks its RSS feed, and downloads a limited number of article HTML snapshots (following redirects) into a structured `samples/` directory for later analysis.
3. Report which journals succeeded/failed during sample collection so operators can retry or mark sources that block scraping.

## Impact
- Creates the metadata + tooling foundation required for per-publisher scraping work.
- Produces deterministic sample files that future parser implementations can reference during development and testing.
- No behavioral change to the production crawl yet; this is preparatory work.
