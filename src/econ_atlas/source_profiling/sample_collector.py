from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Protocol

import httpx
from slugify import slugify

from econ_atlas.models import JournalSource, NormalizedFeedEntry

LOGGER = logging.getLogger(__name__)
DEFAULT_FETCH_TIMEOUT = 30.0
BASE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


class FeedFetcher(Protocol):
    def fetch(self, rss_url: str) -> list[NormalizedFeedEntry]:  # pragma: no cover - protocol signature
        ...


class HtmlFetcher(Protocol):
    def __call__(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        cookies: dict[str, str] | None = None,
    ) -> bytes:  # pragma: no cover
        ...


@dataclass
class FetchRequest:
    url: str
    headers: dict[str, str]
    cookies: dict[str, str] | None


@dataclass
class JournalSampleReport:
    journal: JournalSource
    saved_files: list[Path]
    errors: list[str]

    @property
    def succeeded(self) -> bool:
        return not self.errors


@dataclass
class SampleCollectorReport:
    results: list[JournalSampleReport]

    @property
    def total_saved(self) -> int:
        return sum(len(result.saved_files) for result in self.results)

    @property
    def failures(self) -> list[JournalSampleReport]:
        return [result for result in self.results if result.errors]


class SampleCollector:
    """Downloads article HTML samples for later inspection."""

    def __init__(self, *, feed_client: FeedFetcher, fetch_html: HtmlFetcher | None = None):
        self._feed_client = feed_client
        self._fetch_html = fetch_html or _default_fetch_html

    def collect(
        self,
        journals: Iterable[JournalSource],
        *,
        limit_per_journal: int,
        output_dir: Path,
    ) -> SampleCollectorReport:
        results: list[JournalSampleReport] = []
        output_dir.mkdir(parents=True, exist_ok=True)
        for journal in journals:
            report = self._collect_for_journal(journal, limit_per_journal, output_dir)
            results.append(report)
        return SampleCollectorReport(results=results)

    def _collect_for_journal(
        self,
        journal: JournalSource,
        limit_per_journal: int,
        output_dir: Path,
    ) -> JournalSampleReport:
        try:
            entries = self._feed_client.fetch(journal.rss_url)
        except Exception as exc:  # noqa: BLE001
            LOGGER.error("Failed to fetch RSS for %s: %s", journal.name, exc)
            return JournalSampleReport(journal=journal, saved_files=[], errors=[f"rss: {exc}"])

        target_dir = output_dir / journal.source_type / journal.slug
        target_dir.mkdir(parents=True, exist_ok=True)
        saved_files: list[Path] = []
        errors: list[str] = []
        seen_ids: set[str] = set()

        for entry in entries:
            if limit_per_journal and len(saved_files) >= limit_per_journal:
                break
            entry_id = entry.entry_id or entry.link or ""
            if not entry_id:
                errors.append("missing entry id")
                continue
            if entry_id in seen_ids:
                continue
            seen_ids.add(entry_id)
            if not entry.link:
                errors.append(f"{entry_id}: missing link")
                continue
            request = _build_fetch_request(journal, entry)
            try:
                html_bytes = self._fetch_html(
                    request.url,
                    headers=request.headers,
                    cookies=request.cookies,
                )
            except Exception as exc:  # noqa: BLE001
                LOGGER.warning("Failed to fetch HTML for %s (%s): %s", journal.name, entry.link, exc)
                errors.append(f"{entry_id}: {exc}")
                continue
            filename = _build_filename(entry)
            file_path = target_dir / filename
            file_path.write_bytes(html_bytes)
            saved_files.append(file_path)
        return JournalSampleReport(journal=journal, saved_files=saved_files, errors=errors)


def _default_fetch_html(
    url: str,
    headers: dict[str, str] | None = None,
    cookies: dict[str, str] | None = None,
) -> bytes:
    merged_headers = dict(BASE_HEADERS)
    if headers:
        merged_headers.update(headers)
    cookie_jar = dict(cookies or {})
    # Wiley requires a cookie to signal GDPR consent; emulate default when none provided
    if "onlinelibrary.wiley.com" in url and not cookie_jar:
        cookie_jar["wileyplus-feature-flags"] = "gdpr-ok"
    response = httpx.get(
        url,
        timeout=DEFAULT_FETCH_TIMEOUT,
        headers=merged_headers,
        cookies=cookie_jar or None,
        follow_redirects=True,
    )
    response.raise_for_status()
    return response.content


def _build_filename(entry: NormalizedFeedEntry) -> str:
    raw = entry.entry_id or entry.link or entry.title
    candidate = slugify(raw or "entry", lowercase=True, separator="-")
    if not candidate:
        candidate = slugify(entry.title or "entry", lowercase=True, separator="-") or "entry"
    return f"{candidate}.html"


def _build_fetch_request(journal: JournalSource, entry: NormalizedFeedEntry) -> FetchRequest:
    url = entry.link or entry.entry_id
    if not url:
        raise ValueError("entry link missing")
    headers: dict[str, str] = {}
    if journal.source_type == "wiley":
        url = _rewrite_wiley_url(url)
        headers["Referer"] = "https://onlinelibrary.wiley.com/doi/recent"
    elif journal.source_type == "cambridge":
        headers["Referer"] = "https://www.cambridge.org/"
    elif journal.source_type == "oxford":
        headers["Referer"] = "https://academic.oup.com/"
    elif journal.source_type == "chicago":
        headers["Referer"] = "https://www.journals.uchicago.edu/"
    elif journal.source_type == "sciencedirect":
        headers["Referer"] = "https://www.sciencedirect.com/"
    elif journal.source_type == "informs":
        headers["Referer"] = "https://pubsonline.informs.org/"
    elif journal.source_type == "nber":
        headers["Referer"] = "https://www.nber.org/"
    cookies = _cookies_for_source(journal.source_type)
    return FetchRequest(url=url, headers=headers, cookies=cookies)


def _rewrite_wiley_url(url: str) -> str:
    if "onlinelibrary.wiley.com" not in url:
        return url
    clean = url.split("?", 1)[0]
    marker = "/doi/"
    if marker in clean and "/doi/abs/" not in clean and "/doi/full/" not in clean:
        return clean.replace(marker, "/doi/abs/", 1)
    return clean


def _cookies_for_source(source_type: str) -> dict[str, str] | None:
    env_key = COOKIE_ENV_MAP.get(source_type)
    if not env_key:
        return None
    cookie_text = os.getenv(env_key)
    if not cookie_text:
        return None
    return _parse_cookie_header(cookie_text)


def _parse_cookie_header(value: str) -> dict[str, str]:
    cookies: dict[str, str] = {}
    for chunk in value.split(";"):
        trimmed = chunk.strip()
        if not trimmed:
            continue
        if "=" not in trimmed:
            continue
        name, cookie_value = trimmed.split("=", 1)
        cookies[name.strip()] = cookie_value.strip()
    return cookies
COOKIE_ENV_MAP = {
    "wiley": "WILEY_COOKIES",
    "oxford": "OXFORD_COOKIES",
    "sciencedirect": "SCIENCEDIRECT_COOKIES",
    "chicago": "CHICAGO_COOKIES",
    "informs": "INFORMS_COOKIES",
    "nber": "NBER_COOKIES",
}
