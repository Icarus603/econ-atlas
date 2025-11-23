from __future__ import annotations

import json
import logging
from typing import Any

from bs4 import BeautifulSoup

from econ_atlas.models import ArticleRecord, NormalizedFeedEntry
from econ_atlas.source_profiling.browser_env import (
    browser_credentials_for_source,
    browser_headless_for_source,
    browser_launch_overrides,
    browser_local_storage_for_source,
    browser_user_agent_for_source,
    browser_user_data_dir_for_source,
    browser_wait_selector_for_source,
    build_browser_headers,
    cookies_for_source,
    local_storage_script,
)
from econ_atlas.source_profiling.browser_fetcher import PlaywrightFetcher

LOGGER = logging.getLogger(__name__)
OXFORD_SOURCE_TYPE = "oxford"


class OxfordArticleFetcher:
    def __init__(self, fetcher: PlaywrightFetcher | None = None) -> None:
        self._fetcher = fetcher or PlaywrightFetcher()

    def fetch_html(self, url: str) -> str:
        headers = build_browser_headers({"Referer": "https://academic.oup.com/"}, OXFORD_SOURCE_TYPE)
        cookies = cookies_for_source(OXFORD_SOURCE_TYPE)
        credentials = browser_credentials_for_source(OXFORD_SOURCE_TYPE)
        user_agent = browser_user_agent_for_source(OXFORD_SOURCE_TYPE, headers)
        wait_selector = browser_wait_selector_for_source(OXFORD_SOURCE_TYPE)
        init_scripts = []
        local_storage_entries = browser_local_storage_for_source(OXFORD_SOURCE_TYPE)
        if local_storage_entries:
            init_scripts.append(local_storage_script(local_storage_entries))
        user_data_dir = browser_user_data_dir_for_source(OXFORD_SOURCE_TYPE)
        headless = browser_headless_for_source(OXFORD_SOURCE_TYPE)
        browser_channel, executable_path = browser_launch_overrides(OXFORD_SOURCE_TYPE)
        html_bytes = self._fetcher.fetch(
            url=url,
            headers=headers,
            cookies=cookies,
            credentials=credentials,
            user_agent=user_agent,
            wait_selector=wait_selector,
            extract_script=None,
            init_scripts=init_scripts or None,
            user_data_dir=user_data_dir,
            headless=headless,
            trace_path=None,
            debug_dir=None,
            debug_label=None,
            browser_channel=browser_channel,
            executable_path=executable_path,
        )
        return html_bytes.decode("utf-8", errors="ignore")


class OxfordEnricher:
    def __init__(self, fetcher: OxfordArticleFetcher | None = None) -> None:
        self._fetcher = fetcher or OxfordArticleFetcher()

    def enrich(self, record: ArticleRecord, entry: NormalizedFeedEntry) -> ArticleRecord:
        if record.authors:
            return record
        if not entry.link:
            return record
        try:
            html = self._fetcher.fetch_html(entry.link)
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Oxford fallback failed for %s: %s", entry.link, exc)
            return record
        authors = _extract_authors(html)
        if not authors:
            return record
        return record.model_copy(update={"authors": authors})


def _extract_authors(html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    authors = _authors_from_json_ld(soup)
    if authors:
        return authors
    meta_authors: list[str] = []
    for meta in soup.find_all("meta", attrs={"name": "citation_author"}):
        raw = meta.get("content")
        if isinstance(raw, str):
            trimmed = raw.strip()
            if trimmed:
                meta_authors.append(trimmed)
    return meta_authors


def _authors_from_json_ld(soup: BeautifulSoup) -> list[str]:
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(script.string or "")
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            authors = _coerce_ld_authors(data.get("author"))
            if authors:
                return authors
        elif isinstance(data, list):
            for item in data:
                if not isinstance(item, dict):
                    continue
                authors = _coerce_ld_authors(item.get("author"))
                if authors:
                    return authors
    return []


def _coerce_ld_authors(payload: Any) -> list[str]:
    if not payload:
        return []
    if isinstance(payload, dict):
        name = payload.get("name")
        if isinstance(name, str):
            trimmed = name.strip()
            if trimmed:
                return [trimmed]
        return []
    if isinstance(payload, list):
        result: list[str] = []
        for item in payload:
            result.extend(_coerce_ld_authors(item))
        return result
    if isinstance(payload, str):
        trimmed = payload.strip()
        if trimmed:
            return [trimmed]
    return []
