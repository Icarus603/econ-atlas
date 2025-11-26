from __future__ import annotations

from pathlib import Path

from econatlas.feeds import JournalListLoader, ALLOWED_SOURCE_TYPES


def test_loads_valid_rows(tmp_path: Path) -> None:
    csv_path = tmp_path / "list.csv"
    csv_path.write_text(
        "name,rss,source_type\nTest Journal,https://example.com/rss,sciencedirect\n",
        encoding="utf-8",
    )
    loader = JournalListLoader(csv_path)
    journals = loader.load()
    assert len(journals) == 1
    j = journals[0]
    assert j.name == "Test Journal"
    assert j.rss_url == "https://example.com/rss"
    assert j.source_type == "sciencedirect"
    assert j.slug.startswith("test-journal")


def test_skips_invalid_source(tmp_path: Path) -> None:
    csv_path = tmp_path / "list.csv"
    csv_path.write_text("name,rss,source_type\nBad,,unknown\n", encoding="utf-8")
    loader = JournalListLoader(csv_path)
    journals = loader.load()
    assert journals == []


def test_allowed_sources_contains_expected() -> None:
    assert "sciencedirect" in ALLOWED_SOURCE_TYPES
    assert "oxford" in ALLOWED_SOURCE_TYPES
