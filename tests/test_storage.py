from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from econatlas.models import ArticleRecord, JournalSource, TranslationRecord, TranslationStatus

from econatlas.storage import JournalStore


def _article_with(id_: str, zh: str | None, status: TranslationStatus = "success") -> ArticleRecord:
    return ArticleRecord(
        id=id_,
        title="t",
        link="l",
        authors=["a"],
        published_at=None,
        abstract_original="orig",
        abstract_language="en",
        abstract_zh=zh,
        translation=TranslationRecord(
            status=status, translator="x", translated_at=datetime.now(timezone.utc), error=None
        ),
        fetched_at=datetime.now(timezone.utc),
    )


def test_store_merge_prefers_existing_success(tmp_path: Path) -> None:
    store = JournalStore(tmp_path)
    journal = JournalSource(name="J", rss_url="http://x", slug="j", source_type="sciencedirect")
    existing = _article_with("1", "old", "success")
    new = _article_with("1", None, "failed")
    store.persist(journal, [existing])
    result = store.persist(journal, [new])
    assert result.updated == 0
    data = (tmp_path / "j.json").read_text(encoding="utf-8")
    assert "old" in data


def test_store_adds_and_updates(tmp_path: Path) -> None:
    store = JournalStore(tmp_path)
    journal = JournalSource(name="J", rss_url="http://x", slug="j", source_type="sciencedirect")
    a1 = _article_with("1", None, "failed")
    a2 = _article_with("2", "zh2", "success")
    store.persist(journal, [a1])
    res = store.persist(journal, [a2])
    assert res.added == 1
    assert res.updated == 0


def test_cnki_uses_chinese_filename(tmp_path: Path) -> None:
    store = JournalStore(tmp_path)
    journal = JournalSource(name="中国期刊", rss_url="http://x", slug="irrelevant", source_type="cnki")
    entry = _article_with("1", None, "success")
    store.persist(journal, [entry])
    assert (tmp_path / "中国期刊.json").exists()
