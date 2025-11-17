from __future__ import annotations

from pathlib import Path

from econ_atlas.sources.sciencedirect_parser import parse_sciencedirect_fallback

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "sciencedirect"


def _read_fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


def test_parse_sciencedirect_fallback_full_record() -> None:
    html = _read_fixture("fallback_full.html")
    record = parse_sciencedirect_fallback(
        html, url="https://www.sciencedirect.com/science/article/pii/S0047272725001975"
    )

    assert record.title.value == "Crowding out crowd support?"
    assert record.doi.value == "10.1016/j.jpubeco.2025.102123"
    assert record.pii.value == "S0047272725001975"
    assert record.publication_date.value == "2025-02-15"
    assert record.abstract.value is not None
    assert record.abstract.value.startswith("Paragraph one")
    assert record.keywords.value == ["Informal insurance", "Crowding out", "Social support"]
    assert record.pdf_url.value is not None
    assert record.pdf_url.value.endswith("/pdfft?isDTMRedir=true")
    assert record.missing_fields() == {}

    authors = record.authors.value
    assert authors is not None
    assert [author.name for author in authors] == ["Alice Example", "Bob Example"]
    assert authors[0].affiliations == ["Department of Economics, Sample University"]


def test_parse_sciencedirect_fallback_with_missing_fields() -> None:
    html = _read_fixture("fallback_missing.html")
    record = parse_sciencedirect_fallback(html)

    assert record.title.value == "Trade shocks and households"
    assert record.abstract.value is not None
    assert record.abstract.value.startswith("We document the consumption response")
    assert record.pii.value == "S0167268125004238"
    assert "keywords" in record.missing_fields()
    assert record.pdf_url.source == "inferred"
