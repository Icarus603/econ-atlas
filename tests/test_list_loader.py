from pathlib import Path

from econ_atlas.sources.list_loader import JournalListLoader


def test_list_loader_skips_missing_rss(tmp_path: Path) -> None:
    csv_content = "期刊名称,RSS链接（中文直接在知网上复制RSS链接）,备注\n" "Journal A,https://example.com/rss,ok\n" "Journal B,,missing\n"
    csv_path = tmp_path / "list.csv"
    csv_path.write_text(csv_content, encoding="utf-8")

    loader = JournalListLoader(csv_path)
    journals = loader.load()

    assert len(journals) == 1
    journal = journals[0]
    assert journal.name == "Journal A"
    assert journal.rss_url == "https://example.com/rss"
    assert journal.slug.startswith("journal-a")
