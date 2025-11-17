from __future__ import annotations

from pathlib import Path

import pytest

REQUIRED_FIELDS = [
    "Title",
    "Authors",
    "Affiliations",
    "DOI",
    "Publication date",
    "Abstract",
    "Keywords/JEL",
    "PDF link",
]


def _source_types() -> list[str]:
    samples_dir = Path("samples")
    if not samples_dir.exists():
        return []
    return sorted(child.name for child in samples_dir.iterdir() if child.is_dir() and not child.name.startswith("_"))


@pytest.mark.parametrize("source_type", _source_types())
def test_parser_profile_exists(source_type: str) -> None:
    doc_path = Path("docs/parser_profiles") / f"{source_type}.md"
    assert doc_path.exists(), f"Missing parser profile doc for {source_type}"


@pytest.mark.parametrize("source_type", _source_types())
def test_parser_profile_lists_required_fields(source_type: str) -> None:
    doc_path = Path("docs/parser_profiles") / f"{source_type}.md"
    text = doc_path.read_text(encoding="utf-8")
    for field in REQUIRED_FIELDS:
        needle = f"| {field} |"
        assert needle in text, f"Field '{field}' missing in {doc_path}"
