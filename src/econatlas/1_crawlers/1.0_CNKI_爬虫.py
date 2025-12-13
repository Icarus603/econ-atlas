"""
CNKI 爬虫：直接使用 RSS/JSON 数据，不做额外增强；翻译在后续统一阶段处理。
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from urllib.parse import quote_plus, urlparse

from econatlas._loader import load_local_module
from econatlas.models import ArticleRecord, JournalSource, NormalizedFeedEntry, TranslationRecord

_feed_mod = load_local_module(__file__, "../0_feeds/0.1_RSS_抓取.py", "econatlas._feed_rss")
FeedClient = _feed_mod.FeedClient  # type: ignore[attr-defined]

_trans_mod = load_local_module(__file__, "../3_translation/3.1_翻译基础.py", "econatlas._trans_base")
detect_language = _trans_mod.detect_language  # type: ignore[attr-defined]
skipped_translation = _trans_mod.skipped_translation  # type: ignore[attr-defined]

LOGGER = logging.getLogger(__name__)


class CNKI爬虫:
    """CNKI 来源：仅使用 RSS 内容，不再尝试页面抓取。"""

    def __init__(self, feed_client: FeedClient) -> None:
        self._feed_client = feed_client

    def crawl(self, journal: JournalSource) -> list[ArticleRecord]:
        entries = self._feed_client.fetch(journal.rss_url)
        records: list[ArticleRecord] = []
        for entry in entries:
            record = _构建基础记录(entry)
            records.append(record)
        return records


def _构建基础记录(entry: NormalizedFeedEntry) -> ArticleRecord:
    """将标准化条目转为 ArticleRecord，占位翻译（不立即翻译）。"""
    summary = entry.summary or ""
    language = detect_language(summary)
    translation_result = skipped_translation(summary)
    link = _normalize_cnki_link(entry.link, title=entry.title)
    return ArticleRecord(
        id=entry.entry_id,
        title=entry.title,
        link=link,
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


def _normalize_cnki_link(link: str, *, title: str) -> str:
    """将 CNKI RSS 的短期链接转换为可长期使用的 URL。

    CNKI RSS/列表页常返回 `kcms2/article/abstract?v=...` 这类带 `v` 的链接，
    其中 `v` 参数往往会过期，导致前端“打开原文”变成 404。
    这里优先替换为基于标题的 CNKI 搜索链接，保证可用性。
    """
    raw = (link or "").strip()
    if not raw:
        return ""
    try:
        parsed = urlparse(raw)
    except ValueError:
        return raw
    if not parsed.hostname or not parsed.hostname.endswith(".cnki.net"):
        return raw
    if not parsed.path.startswith("/kcms2/article/abstract"):
        return raw
    if "v=" not in (parsed.query or ""):
        return raw

    query = (title or "").strip()
    if not query:
        return raw
    return f"https://kns.cnki.net/kns8/defaultresult/index?kw={quote_plus(query)}"
