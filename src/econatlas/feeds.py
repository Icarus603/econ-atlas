"""
英文导入入口：封装 0_feeds 包。
"""

from __future__ import annotations

from typing import Any, cast

from econatlas._loader import load_local_module

_feeds_pkg = cast(Any, load_local_module(__file__, "0_feeds/__init__.py", "econatlas._feeds_pkg"))

FeedClient = _feeds_pkg.FeedClient
BrowserFetcher = _feeds_pkg.BrowserFetcher
strip = _feeds_pkg.strip
JournalListLoader = _feeds_pkg.JournalListLoader
ALLOWED_SOURCE_TYPES = _feeds_pkg.ALLOWED_SOURCE_TYPES

__all__ = ["FeedClient", "BrowserFetcher", "strip", "JournalListLoader", "ALLOWED_SOURCE_TYPES"]
