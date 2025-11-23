from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, cast

from econ_atlas.models import ArticleRecord, JournalSource, NormalizedFeedEntry
from econ_atlas.runner import Runner
from econ_atlas.storage.json_store import StorageResult
from econ_atlas.translate.base import TranslationResult, Translator


class StubListLoader:
    def load(self) -> list[JournalSource]:
        return [
            JournalSource(
                name="SciDir Journal",
                rss_url="https://example.com/rss",
                slug="scidir-journal",
                source_type="sciencedirect",
            )
        ]


class StubFeedClient:
    def fetch(self, rss_url: str) -> list[NormalizedFeedEntry]:
        return [
            NormalizedFeedEntry(
                entry_id="entry-1",
                title="Fallback title",
                summary="",
                link="https://www.sciencedirect.com/science/article/pii/S0047272725001975",
                authors=[],
                published_at=datetime.now(timezone.utc),
            )
        ]


class StubTranslator(Translator):
    def translate(self, text: str, *, source_language: str | None = None, target_language: str = "zh") -> TranslationResult:
        return TranslationResult(
            status="skipped",
            translated_text=text,
            translator=None,
            translated_at=datetime.now(timezone.utc),
        )


class StubStore:
    def persist(self, journal: JournalSource, entries: list[ArticleRecord]) -> StorageResult:
        return StorageResult()


class DummyEnricher:
    def __init__(self) -> None:
        self.called = False

    def enrich(self, record: ArticleRecord, entry: NormalizedFeedEntry) -> tuple[ArticleRecord, int, int]:
        self.called = True
        return record, 0, 0


def test_runner_invokes_sciencedirect_enricher() -> None:
    runner = Runner(
        list_loader=cast(Any, StubListLoader()),
        feed_client=cast(Any, StubFeedClient()),
        translator=StubTranslator(),
        store=cast(Any, StubStore()),
    )
    dummy = DummyEnricher()
    runner._scd_enricher = cast(Any, dummy)

    report = runner.run()

    assert dummy.called is True
    assert len(report.results) == 1


class MultiJournalListLoader:
    def load(self) -> list[JournalSource]:
        return [
            JournalSource(
                name="SciDir Journal",
                rss_url="https://example.com/scd",
                slug="scd-journal",
                source_type="sciencedirect",
            ),
            JournalSource(
                name="Wiley Journal",
                rss_url="https://example.com/wiley",
                slug="wiley-journal",
                source_type="wiley",
            ),
        ]


class RecordingFeedClient:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def fetch(self, rss_url: str) -> list[NormalizedFeedEntry]:
        self.calls.append(rss_url)
        return []


class RecordingStore:
    def __init__(self) -> None:
        self.journals: list[str] = []

    def persist(self, journal: JournalSource, entries: list[ArticleRecord]) -> StorageResult:
        self.journals.append(journal.slug)
        return StorageResult()


def test_runner_filters_by_slug() -> None:
    feed_client = RecordingFeedClient()
    store = RecordingStore()
    runner = Runner(
        list_loader=cast(Any, MultiJournalListLoader()),
        feed_client=cast(Any, feed_client),
        translator=StubTranslator(),
        store=cast(Any, store),
        include_slugs={"scd-journal"},
    )

    report = runner.run()

    assert store.journals == ["scd-journal"]
    assert feed_client.calls == ["https://example.com/scd"]
    assert len(report.results) == 1


def test_runner_filters_by_source() -> None:
    feed_client = RecordingFeedClient()
    store = RecordingStore()
    runner = Runner(
        list_loader=cast(Any, MultiJournalListLoader()),
        feed_client=cast(Any, feed_client),
        translator=StubTranslator(),
        store=cast(Any, store),
        include_sources={"wiley"},
    )

    report = runner.run()

    assert store.journals == ["wiley-journal"]
    assert feed_client.calls == ["https://example.com/wiley"]
    assert len(report.results) == 1


def test_runner_filter_without_matches() -> None:
    runner = Runner(
        list_loader=cast(Any, MultiJournalListLoader()),
        feed_client=cast(Any, RecordingFeedClient()),
        translator=StubTranslator(),
        store=cast(Any, RecordingStore()),
        include_slugs={"missing"},
    )

    report = runner.run()

    assert report.results == []
    assert report.errors == ["No journals matched the requested filters"]
    assert report.had_errors is True
