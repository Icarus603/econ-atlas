from __future__ import annotations

import hashlib
import logging
from datetime import datetime
from typing import Any, Iterable, Sequence

import feedparser
import httpx
from dateutil import parser as date_parser

from econ_atlas.models import NormalizedFeedEntry

LOGGER = logging.getLogger(__name__)
USER_AGENT = "econ-atlas/0.1 (+https://github.com/Icarus603/econ-atlas)"


class FeedClient:
    """Fetches RSS/Atom feeds and normalizes entries."""

    def __init__(self, *, timeout: float = 30.0):
        self._timeout = timeout

    def fetch(self, rss_url: str) -> list[NormalizedFeedEntry]:
        LOGGER.info("Fetching feed %s", rss_url)
        response = httpx.get(rss_url, timeout=self._timeout, headers={"User-Agent": USER_AGENT})
        response.raise_for_status()
        parsed = feedparser.parse(response.text)
        if getattr(parsed, "bozo", False):
            LOGGER.warning("Feed %s reported parse issue: %s", rss_url, getattr(parsed, "bozo_exception", "unknown"))
        return [_normalize_entry(entry) for entry in parsed.entries]


def _normalize_entry(entry: Any) -> NormalizedFeedEntry:
    entry_id = (
        _first_non_empty(
            [
                entry.get("id"),
                entry.get("guid"),
                entry.get("link"),
            ]
        )
        or _hash_fallback(entry)
    )
    title = strip(entry.get("title") or "Untitled")
    summary = strip(entry.get("summary") or entry.get("description") or "")
    link = strip(entry.get("link") or "")
    authors = _normalize_authors(entry)
    published_at = _parse_datetime(entry)
    return NormalizedFeedEntry(
        entry_id=entry_id,
        title=title,
        summary=summary,
        link=link,
        authors=authors,
        published_at=published_at,
    )


def _first_non_empty(values: Iterable[str | None]) -> str | None:
    for value in values:
        if value:
            trimmed = value.strip()
            if trimmed:
                return trimmed
    return None


def _hash_fallback(entry: Any) -> str:
    text = f"{entry.get('title','')}|{entry.get('link','')}".encode("utf-8", "ignore")
    digest = hashlib.sha256(text).hexdigest()[:16]
    return f"entry-{digest}"


def strip(value: str) -> str:
    return value.strip()


def _normalize_authors(entry: Any) -> list[str]:
    if "authors" in entry and isinstance(entry["authors"], Sequence):
        normalized = []
        for author_obj in entry["authors"]:
            if isinstance(author_obj, dict):
                name = author_obj.get("name")
                if name:
                    normalized.append(name.strip())
            elif isinstance(author_obj, str):
                normalized.append(author_obj.strip())
        return [name for name in normalized if name]
    author_text = strip(entry.get("author", "") or entry.get("creator", "") or "")
    if not author_text:
        return []
    if ";" in author_text:
        parts = [part.strip() for part in author_text.split(";")]
    elif "," in author_text:
        parts = [part.strip() for part in author_text.split(",")]
    else:
        parts = [author_text]
    return [part for part in parts if part]


def _parse_datetime(entry: Any) -> datetime | None:
    for key in ("published", "updated", "issued"):
        value = entry.get(key)
        if value:
            try:
                return date_parser.parse(value)
            except (ValueError, TypeError):
                continue
    for key in ("published_parsed", "updated_parsed"):
        struct = entry.get(key)
        if struct:
            try:
                return datetime(*struct[:6])
            except (ValueError, TypeError):
                continue
    return None
