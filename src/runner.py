from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from econ_atlas.ingest.feed import FeedClient
from econ_atlas.models import ArticleRecord, JournalSource, NormalizedFeedEntry, TranslationRecord
from econ_atlas.sources.list_loader import JournalListLoader
from econ_atlas.sources.oxford_enricher import OxfordEnricher
from econ_atlas.sources.sciencedirect_api import ElsevierApiConfig, ScienceDirectApiClient
from econ_atlas.sources.sciencedirect_enricher import ScienceDirectEnricher
from econ_atlas.storage.json_store import JournalStore, StorageResult
from econ_atlas.translate.base import Translator, TranslationResult, detect_language, skipped_translation

LOGGER = logging.getLogger(__name__)


@dataclass
class JournalRunResult:
    journal: JournalSource
    fetched: int
    stored: StorageResult
    translation_attempts: int
    translation_failures: int
    error: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.error is None


@dataclass
class RunReport:
    started_at: datetime
    finished_at: datetime
    results: list[JournalRunResult]
    errors: list[str]

    @property
    def total_new_entries(self) -> int:
        return sum(result.stored.added for result in self.results if result.error is None)

    @property
    def total_translation_failures(self) -> int:
        return sum(result.translation_failures for result in self.results if result.error is None)

    @property
    def had_errors(self) -> bool:
        return bool(self.errors or any(not r.succeeded for r in self.results))


class Runner:
    """Coordinates list loading, feed ingestion, translation, and persistence."""

    def __init__(
        self,
        *,
        list_loader: JournalListLoader,
        feed_client: FeedClient,
        translator: Translator,
        store: JournalStore,
        sciencedirect_api_key: str | None = None,
        sciencedirect_inst_token: str | None = None,
        include_slugs: set[str] | None = None,
        include_sources: set[str] | None = None,
        skip_translation: bool = False,
    ) -> None:
        self._list_loader = list_loader
        self._feed_client = feed_client
        self._translator = translator
        self._store = store
        self._include_slugs = include_slugs
        self._include_sources = include_sources
        self._skip_translation = skip_translation
        api_client = None
        if sciencedirect_api_key:
            api_client = ScienceDirectApiClient(
                ElsevierApiConfig(api_key=sciencedirect_api_key, inst_token=sciencedirect_inst_token)
            )
        self._scd_enricher = ScienceDirectEnricher(translator, api_client=api_client)
        self._oxford_enricher = OxfordEnricher()

    def run(self) -> RunReport:
        start = datetime.now(timezone.utc)
        results: list[JournalRunResult] = []
        errors: list[str] = []
        journals = self._list_loader.load()
        LOGGER.info("Loaded %s journals", len(journals))
        journals = self._apply_filters(journals)
        LOGGER.info("After filters: %s journals", len(journals))
        if not journals:
            message = "No journals matched the requested filters"
            LOGGER.warning(message)
            finished = datetime.now(timezone.utc)
            return RunReport(started_at=start, finished_at=finished, results=[], errors=[message])
        for journal in journals:
            try:
                result = self._process_journal(journal)
                results.append(result)
            except Exception as exc:  # noqa: BLE001
                error_message = f"{journal.name}: {exc}"
                LOGGER.exception("Failed to process %s", journal.name)
                errors.append(error_message)
                results.append(
                    JournalRunResult(
                        journal=journal,
                        fetched=0,
                        stored=StorageResult(),
                        translation_attempts=0,
                        translation_failures=0,
                        error=str(exc),
                    )
                )
        finished = datetime.now(timezone.utc)
        try:
            self._oxford_enricher.close()
        except Exception:
            LOGGER.debug("Failed to close Oxford enricher", exc_info=True)
        return RunReport(started_at=start, finished_at=finished, results=results, errors=errors)

    def _apply_filters(self, journals: list[JournalSource]) -> list[JournalSource]:
        filtered = journals
        if self._include_sources:
            filtered = [journal for journal in filtered if journal.source_type in self._include_sources]
        if self._include_slugs:
            filtered = [journal for journal in filtered if journal.slug in self._include_slugs]
        return filtered

    def _process_journal(self, journal: JournalSource) -> JournalRunResult:
        entries = self._feed_client.fetch(journal.rss_url)
        article_records: list[ArticleRecord] = []
        translation_attempts = 0
        translation_failures = 0

        for entry in entries:
            record, attempted, failed = self._build_article(entry)
            if journal.source_type == "sciencedirect":
                record, extra_attempted, extra_failed = self._scd_enricher.enrich(record, entry)
                attempted += extra_attempted
                failed += extra_failed
            elif journal.source_type == "oxford":
                record = self._oxford_enricher.enrich(record, entry)
            article_records.append(record)
            translation_attempts += attempted
            translation_failures += failed

        storage_result = self._store.persist(journal, article_records)
        LOGGER.info(
            "Journal %s processed (%s fetched, %s new)",
            journal.name,
            len(entries),
            storage_result.added,
        )
        return JournalRunResult(
            journal=journal,
            fetched=len(entries),
            stored=storage_result,
            translation_attempts=translation_attempts,
            translation_failures=translation_failures,
        )

    def _build_article(self, entry: NormalizedFeedEntry) -> tuple[ArticleRecord, int, int]:
        summary = entry.summary or ""
        language = detect_language(summary)
        translation_result: TranslationResult
        attempted = 0
        failures = 0

        if self._skip_translation:
            translation_result = TranslationResult(
                status="skipped",
                translated_text=None,
                translator=None,
                translated_at=datetime.now(timezone.utc),
            )
        elif not summary:
            translation_result = skipped_translation(summary)
        elif language and language.startswith("zh"):
            translation_result = skipped_translation(summary)
        else:
            attempted = 1
            translation_result = self._translator.translate(summary, source_language=language or "unknown")
            if translation_result.status == "failed":
                failures = 1

        abstract_zh = translation_result.translated_text if translation_result.translated_text else None
        record = ArticleRecord(
            id=entry.entry_id,
            title=entry.title,
            link=entry.link,
            authors=list(entry.authors),
            published_at=entry.published_at,
            abstract_original=summary or None,
            abstract_language=language,
            abstract_zh=abstract_zh,
            translation=TranslationRecord(
                status=translation_result.status,
                translator=translation_result.translator,
                translated_at=translation_result.translated_at,
                error=translation_result.error,
            ),
            fetched_at=datetime.now(timezone.utc),
        )
        return record, attempted, failures


def run_scheduler(
    runner: Runner,
    interval_seconds: float,
    *,
    on_report: Callable[[RunReport], None] | None = None,
) -> None:
    """Keep invoking the runner until interrupted."""
    LOGGER.info("Starting scheduler every %s seconds", interval_seconds)
    try:
        while True:
            start = time.monotonic()
            report = runner.run()
            if on_report is not None:
                on_report(report)
            else:
                _log_report(report)
            elapsed = time.monotonic() - start
            sleep_for = max(0.0, interval_seconds - elapsed)
            LOGGER.info("Sleeping %.2f seconds before next run", sleep_for)
            time.sleep(sleep_for)
    except KeyboardInterrupt:
        LOGGER.info("Scheduler interrupted by user")


def _log_report(report: RunReport) -> None:
    LOGGER.info(
        "Run completed: %s journals, %s new entries, %s translation failures",
        len(report.results),
        report.total_new_entries,
        report.total_translation_failures,
    )
