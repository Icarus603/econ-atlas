from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

from econ_atlas.models import ArticleRecord, NormalizedFeedEntry, TranslationRecord
from econ_atlas.sources.sciencedirect_api import ScienceDirectApiError
from econ_atlas.sources.sciencedirect_enricher import ScienceDirectEnricher
from econ_atlas.translate.base import TranslationResult

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "sciencedirect"


class StubFetcher:
    def __init__(self, html: str | Exception):
        self._html = html

    def fetch_html(self, url: str) -> str:
        if isinstance(self._html, Exception):
            raise self._html
        return self._html


class StubTranslator:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def translate(self, text: str, *, source_language: str | None = None, target_language: str = "zh") -> TranslationResult:
        self.calls.append(text)
        return TranslationResult(
            status="success",
            translated_text=f"ZH:{text}",
            translator="stub",
            translated_at=datetime.now(timezone.utc),
        )


def _base_record() -> ArticleRecord:
    return ArticleRecord(
        id="S0047272725001975",
        title="Old",
        link="https://www.sciencedirect.com/science/article/pii/S0047272725001975",
        authors=[],
        published_at=None,
        abstract_original=None,
        abstract_language=None,
        abstract_zh=None,
        translation=TranslationRecord(status="skipped", translator=None, translated_at=datetime.now(timezone.utc)),
        fetched_at=datetime.now(timezone.utc),
    )


def _entry() -> NormalizedFeedEntry:
    return NormalizedFeedEntry(
        entry_id="S0047272725001975",
        title="",
        summary="",
        link="https://www.sciencedirect.com/science/article/pii/S0047272725001975",
        authors=[],
        published_at=None,
    )


def test_api_enrich_updates_fields() -> None:
    payload_text = (FIXTURE_DIR / "api_response.json").read_text(encoding="utf-8")
    stub_payload = cast(dict[str, Any], json.loads(payload_text))
    api_client = cast(Any, StubApiClient(stub_payload))
    translator = StubTranslator()
    enricher = ScienceDirectEnricher(translator, api_client=api_client)

    record, attempts, failures = enricher.enrich(_base_record(), _entry())

    assert api_client.calls == ["S0047272725001975"]
    assert record.title == "API Crowding out crowd support?"
    assert record.authors == ["Alice Example", "Bob Example"]
    assert record.published_at is not None
    assert record.abstract_original is not None
    assert record.abstract_original.startswith("API abstract")
    assert attempts == 1
    assert failures == 0
    assert len(translator.calls) == 1


def test_api_failure_falls_back_to_dom() -> None:
    html = (FIXTURE_DIR / "fallback_full.html").read_text(encoding="utf-8")
    fetcher = StubFetcher(html)
    translator = StubTranslator()
    api_client = cast(Any, StubApiClient(ScienceDirectApiError("boom")))
    enricher = ScienceDirectEnricher(translator, api_client=api_client, fetcher=fetcher)

    record, attempts, failures = enricher.enrich(_base_record(), _entry())

    assert attempts == 1
    assert failures == 0
    assert record.title == "Crowding out crowd support?"
    assert record.authors == ["Alice Example", "Bob Example"]
    assert record.published_at is not None
    assert record.abstract_original is not None
    assert record.abstract_original.startswith("Paragraph one")
    assert record.abstract_zh is not None
    assert len(translator.calls) == 1
    assert record.translation.status == "success"


def test_dom_enrich_skips_when_fetch_fails() -> None:
    fetcher = StubFetcher(RuntimeError("missing profile"))
    translator = StubTranslator()
    enricher = ScienceDirectEnricher(translator, api_client=None, fetcher=fetcher)

    base_record = _base_record()
    record, attempts, failures = enricher.enrich(base_record, _entry())

    assert attempts == 0
    assert failures == 0
    assert record.title == base_record.title
    assert translator.calls == []


def test_dom_enrich_does_not_retranslate_same_abstract() -> None:
    html = (FIXTURE_DIR / "fallback_full.html").read_text(encoding="utf-8")
    fetcher = StubFetcher(html)
    translator = StubTranslator()
    enricher = ScienceDirectEnricher(translator, api_client=None, fetcher=fetcher)

    existing = _base_record().model_copy(
        update={
            "abstract_original": (
                "Paragraph one explains the measurement of informal support.\n\n"
                "Paragraph two states that we observe displacement effects."
            )
        }
    )

    record, attempts, failures = enricher.enrich(existing, _entry())

    assert attempts == 0
    assert failures == 0
    assert record.abstract_original == existing.abstract_original
    assert translator.calls == []
class StubApiClient:
    def __init__(self, payload: dict[str, Any] | Exception):
        self.payload = payload
        self.calls: list[str] = []

    def fetch_by_pii(self, pii: str) -> dict[str, Any]:
        self.calls.append(pii)
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload
