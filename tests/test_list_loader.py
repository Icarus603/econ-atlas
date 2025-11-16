from pathlib import Path

from econ_atlas.sources.list_loader import ALLOWED_SOURCE_TYPES, JournalListLoader


def test_list_loader_skips_missing_rss(tmp_path: Path) -> None:
    csv_content = (
        "期刊名称,RSS链接（中文直接在知网上复制RSS链接）,备注,source_type\n"
        "Journal A,https://example.com/rss,ok,wiley\n"
        "Journal B,,missing,wiley\n"
    )
    csv_path = tmp_path / "list.csv"
    csv_path.write_text(csv_content, encoding="utf-8")

    loader = JournalListLoader(csv_path)
    journals = loader.load()

    assert len(journals) == 1
    journal = journals[0]
    assert journal.name == "Journal A"
    assert journal.rss_url == "https://example.com/rss"
    assert journal.slug.startswith("journal-a")
    assert journal.source_type == "wiley"


def test_list_loader_rejects_invalid_source_type(tmp_path: Path) -> None:
    csv_content = (
        "期刊名称,RSS链接（中文直接在知网上复制RSS链接）,备注,source_type\n"
        "Journal A,https://example.com/rss,ok,unknown\n"
    )
    csv_path = tmp_path / "list.csv"
    csv_path.write_text(csv_content, encoding="utf-8")

    loader = JournalListLoader(csv_path)
    journals = loader.load()

    assert journals == []
    # sanity check allowed set not empty
    assert "cnki" in ALLOWED_SOURCE_TYPES
