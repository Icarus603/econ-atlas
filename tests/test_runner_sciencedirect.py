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
