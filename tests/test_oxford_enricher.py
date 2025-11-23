from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, cast

from econ_atlas.models import ArticleRecord, NormalizedFeedEntry, TranslationRecord
from econ_atlas.sources.oxford_enricher import OxfordEnricher


HTML_DOC = """
<!DOCTYPE html>
<html>
  <head>
    <script type="application/ld+json">
    {
      "@context":"https://schema.org",
      "@type":"ScholarlyArticle",
      "author":[{"name":"Alice"},{"name":"Bob"}]
    }
    </script>
  </head>
  <body></body>
</html>
"""


class StubFetcher:
    def __init__(self, html: str | Exception):
        self.html = html

    def fetch_html(self, url: str) -> str:
        if isinstance(self.html, Exception):
            raise self.html
        return self.html


def _base_record() -> ArticleRecord:
    return ArticleRecord(
        id="doi",
        title="Title",
        link="https://example.com",
        authors=[],
        published_at=datetime.now(timezone.utc),
        abstract_original="",
        abstract_language=None,
        abstract_zh=None,
        translation=TranslationRecord(
            status="skipped",
            translator=None,
            translated_at=datetime.now(timezone.utc),
        ),
        fetched_at=datetime.now(timezone.utc),
    )


def _entry() -> NormalizedFeedEntry:
    return NormalizedFeedEntry(
        entry_id="doi",
        title="Title",
        summary="",
        link="https://example.com",
        authors=[],
        published_at=datetime.now(timezone.utc),
    )


def test_oxford_enricher_updates_authors() -> None:
    enricher = OxfordEnricher(fetcher=cast(Any, StubFetcher(HTML_DOC)))
    record = enricher.enrich(_base_record(), _entry())
    assert record.authors == ["Alice", "Bob"]


def test_oxford_enricher_handles_failures() -> None:
    enricher = OxfordEnricher(fetcher=cast(Any, StubFetcher(RuntimeError("boom"))))
    record = enricher.enrich(_base_record(), _entry())
    assert record.authors == []
