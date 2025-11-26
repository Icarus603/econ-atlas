"""
Oxford 爬虫：RSS 获取后用浏览器抓取作者，翻译另行处理。
"""

from __future__ import annotations

from datetime import datetime, timezone

from econatlas._loader import load_local_module
from econatlas.models import ArticleRecord, JournalSource, NormalizedFeedEntry, TranslationRecord

_enricher = load_local_module(__file__, "../2_enrichers/2.2_Oxford_增强器.py", "econatlas._enricher_oxford")
OxfordEnricher = _enricher.OxfordEnricher  # type: ignore[attr-defined]

_feed_mod = load_local_module(__file__, "../0_feeds/0.1_RSS_抓取.py", "econatlas._feed_rss")
FeedClient = _feed_mod.FeedClient  # type: ignore[attr-defined]

_trans_mod = load_local_module(__file__, "../3_translation/3.1_翻译基础.py", "econatlas._trans_base")
detect_language = _trans_mod.detect_language  # type: ignore[attr-defined]
skipped_translation = _trans_mod.skipped_translation  # type: ignore[attr-defined]


class Oxford爬虫:
    """Oxford 来源：RSS + 浏览器补全作者。"""

    def __init__(self, feed_client: FeedClient) -> None:
        self._feed_client = feed_client
        self._enricher = OxfordEnricher()

    def crawl(self, journal: JournalSource) -> list[ArticleRecord]:
        entries = self._feed_client.fetch(journal.rss_url)
        records: list[ArticleRecord] = []
        for entry in entries:
            record = _构建基础记录(entry)
            record = self._enricher.enrich(record, entry)
            records.append(record)
        return records

    def close(self) -> None:
        try:
            self._enricher.close()
        except Exception:
            pass


def _构建基础记录(entry: NormalizedFeedEntry) -> ArticleRecord:
    """将标准化条目转为 ArticleRecord，占位翻译（不立即翻译）。"""
    summary = entry.summary or ""
    language = detect_language(summary)
    translation_result = skipped_translation(summary)
    return ArticleRecord(
        id=entry.entry_id,
        title=entry.title,
        link=entry.link,
        authors=list(entry.authors),
        published_at=entry.published_at,
        abstract_original=summary or None,
        abstract_language=language,
        abstract_zh=None,
        translation=TranslationRecord(
            status=translation_result.status,
            translator=translation_result.translator,
            translated_at=translation_result.translated_at,
            error=translation_result.error,
        ),
        fetched_at=datetime.now(timezone.utc),
    )
