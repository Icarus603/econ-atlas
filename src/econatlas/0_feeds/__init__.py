"""
Feed 抓取与标准化入口。
"""

from __future__ import annotations

from econatlas._loader import load_local_module

_list_mod = load_local_module(__file__, "0.0_期刊列表.py", "econatlas._feeds_list")
_rss = load_local_module(__file__, "0.1_RSS_抓取.py", "econatlas._feeds_rss")

JournalListLoader = _list_mod.JournalListLoader  # type: ignore[attr-defined]
ALLOWED_SOURCE_TYPES = _list_mod.ALLOWED_SOURCE_TYPES  # type: ignore[attr-defined]

FeedClient = _rss.FeedClient  # type: ignore[attr-defined]
BrowserFetcher = _rss.BrowserFetcher  # type: ignore[attr-defined]
strip = _rss.strip  # type: ignore[attr-defined]

__all__ = ["FeedClient", "BrowserFetcher", "strip", "JournalListLoader", "ALLOWED_SOURCE_TYPES"]
