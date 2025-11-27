"""
ScienceDirect 爬虫：拉取 RSS/JSON feed，调用 Elsevier API 进行元数据增强（不做翻译）。
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone

from econatlas._loader import load_local_module
from econatlas.models import ArticleRecord, JournalSource, NormalizedFeedEntry, TranslationRecord

_enricher = load_local_module(__file__, "../2_enrichers/2.1_ScienceDirect_增强器.py", "econatlas._enricher_scd")
ElsevierApiConfig = _enricher.ElsevierApiConfig  # type: ignore[attr-defined]
ScienceDirectApiClient = _enricher.ScienceDirectApiClient  # type: ignore[attr-defined]
ScienceDirectEnricher = _enricher.ScienceDirectEnricher  # type: ignore[attr-defined]

_feed_mod = load_local_module(__file__, "../0_feeds/0.1_RSS_抓取.py", "econatlas._feed_rss")
FeedClient = _feed_mod.FeedClient  # type: ignore[attr-defined]

_trans_mod = load_local_module(__file__, "../3_translation/3.1_翻译基础.py", "econatlas._trans_base")
detect_language = _trans_mod.detect_language  # type: ignore[attr-defined]
skipped_translation = _trans_mod.skipped_translation  # type: ignore[attr-defined]

LOGGER = logging.getLogger(__name__)


class ScienceDirect爬虫:
    """ScienceDirect 来源的抓取与增强。"""

    def __init__(self, feed_client: FeedClient, api_key: str | None, inst_token: str | None) -> None:
        self._feed_client = feed_client
        self._enricher: ScienceDirectEnricher | None = None
        self._throttle_seconds = _throttle_seconds_from_env()
        if api_key:
            self._enricher = ScienceDirectEnricher(
                api_client=ScienceDirectApiClient(ElsevierApiConfig(api_key=api_key, inst_token=inst_token))
            )

    def crawl(self, journal: JournalSource) -> list[ArticleRecord]:
        entries = self._feed_client.fetch(journal.rss_url)
        records: list[ArticleRecord] = []
        for entry in entries:
            if self._throttle_seconds > 0:
                time.sleep(self._throttle_seconds)
            record = _构建基础记录(entry)
            if self._enricher:
                record, _, _ = self._enricher.enrich(record, entry)
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


def _throttle_seconds_from_env() -> float:
    raw = os.getenv("SCIENCEDIRECT_THROTTLE_SECONDS")
    if not raw:
        return 0.0
    try:
        value = float(raw)
        return value if value > 0 else 0.0
    except ValueError:
        LOGGER.warning("Invalid SCIENCEDIRECT_THROTTLE_SECONDS value: %s", raw)
        return 0.0
