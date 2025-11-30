"""
CNKI 爬虫：直接使用 RSS/JSON 数据，不做额外增强；翻译在后续统一阶段处理。
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from econatlas._loader import load_local_module
from econatlas.models import ArticleRecord, JournalSource, NormalizedFeedEntry, TranslationRecord

_enricher_mod = load_local_module(__file__, "../2_enrichers/2.3_CNKI_增强器.py", "econatlas._enricher_cnki")
CNKIEnricher = _enricher_mod.CNKIEnricher  # type: ignore[attr-defined]

_feed_mod = load_local_module(__file__, "../0_feeds/0.1_RSS_抓取.py", "econatlas._feed_rss")
FeedClient = _feed_mod.FeedClient  # type: ignore[attr-defined]

_trans_mod = load_local_module(__file__, "../3_translation/3.1_翻译基础.py", "econatlas._trans_base")
detect_language = _trans_mod.detect_language  # type: ignore[attr-defined]
skipped_translation = _trans_mod.skipped_translation  # type: ignore[attr-defined]

LOGGER = logging.getLogger(__name__)


class CNKI爬虫:
    """CNKI 来源：直接拉取 feed 并构建记录。"""

    def __init__(self, feed_client: FeedClient) -> None:
        self._feed_client = feed_client
        self._enricher = CNKIEnricher()

    def crawl(self, journal: JournalSource) -> list[ArticleRecord]:
        entries = self._feed_client.fetch(journal.rss_url)
        records: list[ArticleRecord] = []
        for entry in entries:
            record = _构建基础记录(entry)
            record = self._enricher.enrich(record, entry)
            records.append(record)
        return records


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
