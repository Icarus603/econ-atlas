from datetime import datetime, timezone
from pathlib import Path

from econ_atlas.models import ArticleRecord, JournalSource, TranslationRecord, TranslationStatus
from econ_atlas.storage.json_store import JournalStore


def _sample_entry(status: TranslationStatus, abstract_zh: str | None) -> ArticleRecord:
    now = datetime(2024, 1, 1, tzinfo=timezone.utc)
    return ArticleRecord(
        id="entry-1",
        title="Sample",
        link="https://example.com/a",
        authors=["Author"],
        published_at=now,
        abstract_original="Hello world",
        abstract_language="en",
        abstract_zh=abstract_zh,
        translation=TranslationRecord(
            status=status,
            translator="deepseek",
            translated_at=now,
            error=None if status == "success" else "error",
        ),
        fetched_at=now,
    )


def test_storage_adds_and_updates_entries(tmp_path: Path) -> None:
    store = JournalStore(tmp_path)
    journal = JournalSource(name="Journal", rss_url="https://example.com/rss", slug="journal")

    first = _sample_entry("failed", None)
    result = store.persist(journal, [first])
    assert result.added == 1
    assert result.updated == 0

    # Same entry but with translated text should update instead of add.
    second = _sample_entry("success", "translated text")
    result2 = store.persist(journal, [second])
    assert result2.added == 0
    assert result2.updated == 1

    # Loading again should show the merged translation.
    archive_path = tmp_path / "journal.json"
    data = archive_path.read_text(encoding="utf-8")
    assert "translated text" in data
