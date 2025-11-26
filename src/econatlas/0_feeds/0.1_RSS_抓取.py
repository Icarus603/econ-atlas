"""
RSS/JSON 抓取与标准化：处理受保护站点时可调用浏览器抓取。
"""

from __future__ import annotations

import hashlib
import logging
import json
import os
from datetime import datetime
from typing import Any, Iterable, Sequence, Protocol
from urllib.parse import urlparse

import feedparser
import httpx
from dateutil import parser as date_parser

from econatlas.models import NormalizedFeedEntry
from econatlas.samples import BrowserCredentials, PlaywrightFetcher

LOGGER = logging.getLogger(__name__)
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)
BASE_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}
FEED_HEADER_OVERRIDES = {
    "www.journals.uchicago.edu": {
        "Referer": "https://www.journals.uchicago.edu/",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "zh-HK,zh;q=0.9,en-US;q=0.8,en;q=0.7,zh-TW;q=0.6,zh-CN;q=0.5",
        "Cache-Control": "max-age=0",
        "Sec-Ch-Ua": '"Chromium";v="142", "Google Chrome";v="142", "Not_A Brand";v="99"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"macOS"',
        "Sec-Ch-Ua-Platform-Version": '"15.7.1"',
        "Sec-Ch-Ua-Arch": '"arm"',
        "Sec-Ch-Ua-Bitness": '"64"',
        "Sec-Ch-Ua-Full-Version": '"142.0.7444.162"',
        "Sec-Ch-Ua-Full-Version-List": '"Chromium";v="142.0.7444.162", "Google Chrome";v="142.0.7444.162", "Not_A Brand";v="99.0.0.0"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
    },
    "pubsonline.informs.org": {"Referer": "https://pubsonline.informs.org/"},
}
FEED_COOKIE_ENV_MAP = {
    "www.journals.uchicago.edu": "CHICAGO_COOKIES",
    "pubsonline.informs.org": "INFORMS_COOKIES",
    "www.nber.org": "NBER_COOKIES",
}
JSON_KEYS = ("items", "results", "data", "entries", "documents")
PROTECTED_FEED_HOSTS = frozenset({"www.journals.uchicago.edu", "pubsonline.informs.org"})


class BrowserFetcher(Protocol):
    def fetch(
        self,
        *,
        url: str,
        headers: dict[str, str],
        cookies: dict[str, str] | None,
        credentials: BrowserCredentials | None,
        user_agent: str,
    ) -> bytes:
        ...


class FeedClient:
    """拉取 RSS/Atom 或 JSON feed，并输出标准化条目。"""

    def __init__(
        self,
        *,
        timeout: float = 30.0,
        browser_fetcher: BrowserFetcher | None = None,
        protected_hosts: Iterable[str] | None = None,
    ):
        self._timeout = timeout
        self._browser_fetcher: BrowserFetcher | None = browser_fetcher
        self._protected_hosts = set(protected_hosts) if protected_hosts else set(PROTECTED_FEED_HOSTS)

    def fetch(self, rss_url: str) -> list[NormalizedFeedEntry]:
        LOGGER.info("抓取 feed %s", rss_url)
        headers = _headers_for_feed(rss_url)
        cookies = _cookies_for_feed(rss_url)
        host = urlparse(rss_url).hostname or ""
        if host in self._protected_hosts:
            text = self._fetch_feed_via_browser(rss_url, headers=headers, cookies=cookies)
            if _looks_like_json_text(text):
                return self._parse_json_payload(rss_url, text)
            return self._parse_rss_feed(rss_url, text)

        response = httpx.get(
            rss_url,
            timeout=self._timeout,
            headers=headers,
            cookies=cookies or None,
        )
        response.raise_for_status()
        if _looks_like_json(response):
            return self._parse_json_payload(rss_url, response.text)
        return self._parse_rss_feed(rss_url, response.text)

    def _parse_rss_feed(self, rss_url: str, text: str) -> list[NormalizedFeedEntry]:
        parsed = feedparser.parse(text)
        if getattr(parsed, "bozo", False):
            LOGGER.warning("Feed %s 解析异常: %s", rss_url, getattr(parsed, "bozo_exception", "unknown"))
        return [_normalize_entry(entry) for entry in parsed.entries]

    def _parse_json_payload(self, rss_url: str, text: str) -> list[NormalizedFeedEntry]:
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            LOGGER.error("Feed %s 返回非法 JSON: %s", rss_url, exc)
            return []
        raw_entries = _extract_json_entries(payload)
        if not raw_entries:
            LOGGER.warning("Feed %s JSON 未包含 entries", rss_url)
            return []
        normalized: list[NormalizedFeedEntry] = []
        base_url = _base_url(rss_url)
        for entry in raw_entries:
            if not isinstance(entry, dict):
                continue
            normalized.append(_normalize_json_entry(entry, base_url=base_url))
        return normalized

    def _fetch_feed_via_browser(
        self,
        rss_url: str,
        *,
        headers: dict[str, str],
        cookies: dict[str, str] | None,
    ) -> str:
        fetcher = self._ensure_browser_fetcher()
        user_agent = headers.get("User-Agent", USER_AGENT)
        host = urlparse(rss_url).hostname or ""
        home_url = _home_url_for_host(host)
        try:
            if home_url:
                fetcher.fetch(
                    url=home_url,
                    headers=headers,
                    cookies=cookies,
                    credentials=None,
                    user_agent=user_agent,
                )
            html_bytes = fetcher.fetch(
                url=rss_url,
                headers=headers,
                cookies=cookies,
                credentials=None,
                user_agent=user_agent,
            )
        except Exception as exc:  # noqa: BLE001
            LOGGER.error("浏览器抓取失败 %s: %s", rss_url, exc)
            raise
        return html_bytes.decode("utf-8", errors="ignore")

    def _ensure_browser_fetcher(self) -> BrowserFetcher:
        if self._browser_fetcher is None:
            fetcher: BrowserFetcher = PlaywrightFetcher()
            self._browser_fetcher = fetcher
        assert self._browser_fetcher is not None
        return self._browser_fetcher


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
    authors_field = entry.get("authors")
    if isinstance(authors_field, Sequence) and not isinstance(authors_field, (str, bytes)):
        normalized = []
        for author_obj in authors_field:
            if isinstance(author_obj, dict):
                name = author_obj.get("name")
                if name:
                    normalized.append(name.strip())
            elif isinstance(author_obj, str):
                normalized.append(author_obj.strip())
        normalized = [name for name in normalized if name]
        if normalized:
            return normalized

    for key in ("author", "creator", "dc_creator", "dc:creator"):
        raw_value = entry.get(key)
        if not raw_value:
            continue
        normalized = _coerce_author_values(raw_value)
        if normalized:
            return normalized
    return []


def _coerce_author_values(value: Any) -> list[str]:
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        if ";" in text:
            candidates = [part.strip() for part in text.split(";")]
        elif "," in text:
            candidates = [part.strip() for part in text.split(",")]
        else:
            candidates = [text]
        return [candidate for candidate in candidates if candidate]
    if isinstance(value, Sequence):
        results: list[str] = []
        for item in value:
            results.extend(_coerce_author_values(item))
        return results
    if isinstance(value, dict):
        name = value.get("name") or value.get("dc:creator") or value.get("$")
        if isinstance(name, str) and name.strip():
            return [name.strip()]
    return []


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


def _normalize_json_entry(entry: dict[str, Any], *, base_url: str | None) -> NormalizedFeedEntry:
    entry_id = _first_json_value(
        entry,
        [
            "id",
            "paper_id",
            "paperId",
            "identifier",
            "slug",
            "name",
        ],
    )
    link = _first_json_value(entry, ["permalink", "url", "link", "html_url"])
    if link:
        link = _absolute_url(base_url, link)
    title = _first_json_value(entry, ["title", "name"]) or "Untitled"
    summary = _first_json_value(entry, ["summary", "abstract", "description"]) or ""
    authors = _json_authors(entry)
    published_text = _first_json_value(
        entry,
        [
            "public_date",
            "published",
            "published_at",
            "publicationDate",
            "publication_date",
            "date",
            "release_date",
        ],
    )
    published_at = _parse_json_datetime(published_text)
    if not entry_id:
        entry_id = _hash_json_entry(entry, link, title)
    return NormalizedFeedEntry(
        entry_id=entry_id,
        title=title,
        summary=summary,
        link=link or "",
        authors=authors,
        published_at=published_at,
    )


def _json_authors(entry: dict[str, Any]) -> list[str]:
    authors = entry.get("authors") or entry.get("author_list")
    if isinstance(authors, list):
        normalized: list[str] = []
        for item in authors:
            if isinstance(item, dict):
                name = item.get("full_name") or item.get("name") or item.get("author")
                if name:
                    normalized.append(name.strip())
            elif isinstance(item, str):
                stripped = item.strip()
                if stripped:
                    normalized.append(stripped)
        return normalized
    if isinstance(authors, str):
        stripped = authors.strip()
        return [stripped] if stripped else []
    return []


def _parse_json_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return date_parser.parse(value)
    except (ValueError, TypeError):
        return None


def _hash_json_entry(entry: dict[str, Any], link: str | None, title: str) -> str:
    base = json.dumps(
        {
            "title": title,
            "link": link or "",
            "id": entry.get("id") or "",
        },
        sort_keys=True,
    ).encode("utf-8", "ignore")
    digest = hashlib.sha256(base).hexdigest()[:16]
    return f"entry-{digest}"


def _first_json_value(entry: dict[str, Any], keys: list[str]) -> str | None:
    for key in keys:
        value = entry.get(key)
        if not value:
            continue
        if isinstance(value, str):
            stripped = value.strip()
            if stripped:
                return stripped
        elif isinstance(value, (int, float)):
            return str(value)
    return None


def _extract_json_entries(payload: Any) -> list[Any]:
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []
    for key in JSON_KEYS:
        value = payload.get(key)
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            nested = _extract_json_entries(value)
            if nested:
                return nested
    for value in payload.values():
        if isinstance(value, dict):
            nested = _extract_json_entries(value)
            if nested:
                return nested
    return []


def _headers_for_feed(rss_url: str) -> dict[str, str]:
    headers = dict(BASE_HEADERS)
    host = urlparse(rss_url).hostname or ""
    overrides = FEED_HEADER_OVERRIDES.get(host)
    if overrides:
        headers.update(overrides)
    return headers


def _cookies_for_feed(rss_url: str) -> dict[str, str] | None:
    host = urlparse(rss_url).hostname or ""
    env_key = FEED_COOKIE_ENV_MAP.get(host)
    if not env_key:
        return None
    cookie_text = os.getenv(env_key)
    if not cookie_text:
        return None
    return _parse_cookie_header(cookie_text)


def _parse_cookie_header(value: str) -> dict[str, str]:
    cookies: dict[str, str] = {}
    cleaned = value.strip().strip("\"'")
    for chunk in cleaned.split(";"):
        trimmed = chunk.strip()
        if not trimmed or "=" not in trimmed:
            continue
        name, cookie_value = trimmed.split("=", 1)
        cookies[name.strip().strip('\"\'')] = cookie_value.strip().strip('\"\'')
    return cookies


def _looks_like_json(response: httpx.Response) -> bool:
    content_type = response.headers.get("Content-Type", "").lower()
    if "json" in content_type:
        return True
    text = response.text.lstrip()
    return text.startswith("{") or text.startswith("[")


def _looks_like_json_text(text: str) -> bool:
    return text.lstrip().startswith("{") or text.lstrip().startswith("[")


def _base_url(rss_url: str) -> str | None:
    parsed = urlparse(rss_url)
    if not parsed.scheme or not parsed.netloc:
        return None
    return f"{parsed.scheme}://{parsed.netloc}"


def _absolute_url(base_url: str | None, link: str) -> str:
    if link.startswith("http://") or link.startswith("https://"):
        return link
    if base_url:
        if link.startswith("/"):
            return f"{base_url}{link}"
        return f"{base_url.rstrip('/')}/{link}"
    return link


def _home_url_for_host(host: str) -> str | None:
    if host == "www.journals.uchicago.edu":
        return "https://www.journals.uchicago.edu/"
    if host == "pubsonline.informs.org":
        return "https://pubsonline.informs.org/"
    return None
