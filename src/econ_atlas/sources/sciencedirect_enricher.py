from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any, Protocol

from dateutil import parser as date_parser

from econ_atlas.models import ArticleRecord, NormalizedFeedEntry, TranslationRecord
from econ_atlas.source_profiling.browser_env import (
    BrowserLaunchConfigurationError,
    browser_credentials_for_source,
    browser_extract_script_for_source,
    browser_headless_for_source,
    browser_init_scripts_for_source,
    browser_launch_overrides,
    browser_local_storage_for_source,
    browser_user_agent_for_source,
    browser_user_data_dir_for_source,
    browser_wait_selector_for_source,
    build_browser_headers,
    cookies_for_source,
    local_storage_script,
    rewrite_sciencedirect_url,
    require_sciencedirect_profile,
)
from econ_atlas.source_profiling.browser_fetcher import PlaywrightFetcher
from econ_atlas.sources.sciencedirect_api import ScienceDirectApiClient, ScienceDirectApiError
from econ_atlas.sources.sciencedirect_parser import ScienceDirectParsedArticle, parse_sciencedirect_fallback
from econ_atlas.translate.base import Translator, detect_language, skipped_translation
from econ_atlas.translate.base import TranslationResult

LOGGER = logging.getLogger(__name__)
SCIENCEDIRECT_SOURCE_TYPE = "sciencedirect"
PII_REGEX = re.compile(r"/pii/([^/?#]+)", re.IGNORECASE)


class HtmlFetcher(Protocol):
    def fetch_html(self, url: str) -> str:  # pragma: no cover - protocol definition
        ...


class ScienceDirectArticleFetcher:
    """Fetches ScienceDirect article HTML via Playwright."""

    def __init__(self, *, fetcher: PlaywrightFetcher | None = None):
        self._fetcher = fetcher or PlaywrightFetcher()

    def fetch_html(self, url: str) -> str:
        canonical = rewrite_sciencedirect_url(url)
        headers = build_browser_headers({"Referer": "https://www.sciencedirect.com/"}, SCIENCEDIRECT_SOURCE_TYPE)
        cookies = cookies_for_source(SCIENCEDIRECT_SOURCE_TYPE)
        credentials = browser_credentials_for_source(SCIENCEDIRECT_SOURCE_TYPE)
        user_agent = browser_user_agent_for_source(SCIENCEDIRECT_SOURCE_TYPE, headers)
        wait_selector = browser_wait_selector_for_source(SCIENCEDIRECT_SOURCE_TYPE)
        extract_script = browser_extract_script_for_source(SCIENCEDIRECT_SOURCE_TYPE)
        init_scripts = browser_init_scripts_for_source(SCIENCEDIRECT_SOURCE_TYPE)
        local_storage_entries = browser_local_storage_for_source(SCIENCEDIRECT_SOURCE_TYPE)
        if local_storage_entries:
            init_scripts.append(local_storage_script(local_storage_entries))
        user_data_dir = browser_user_data_dir_for_source(SCIENCEDIRECT_SOURCE_TYPE)
        user_data_dir = require_sciencedirect_profile(user_data_dir)
        headless = browser_headless_for_source(SCIENCEDIRECT_SOURCE_TYPE)
        browser_channel, executable_path = browser_launch_overrides(SCIENCEDIRECT_SOURCE_TYPE)
        html_bytes = self._fetcher.fetch(
            url=canonical,
            headers=headers,
            cookies=cookies,
            credentials=credentials,
            user_agent=user_agent,
            wait_selector=wait_selector,
            extract_script=extract_script,
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


class ScienceDirectEnricher:
    """Prefers Elsevier API; falls back to DOM parsing when unavailable."""

    def __init__(
        self,
        translator: Translator,
        *,
        api_client: ScienceDirectApiClient | None = None,
        fetcher: HtmlFetcher | None = None,
    ) -> None:
        self._translator = translator
        self._api_client = api_client
        self._dom_enricher = _ScienceDirectDomEnricher(translator, fetcher=fetcher)

    def enrich(
        self,
        record: ArticleRecord,
        entry: NormalizedFeedEntry,
    ) -> tuple[ArticleRecord, int, int]:
        if self._api_client is not None:
            pii = _pii_from_entry(entry)
            if pii:
                try:
                    payload = self._api_client.fetch_by_pii(pii)
                    api_result = self._apply_api_payload(record, payload)
                    if api_result is not None:
                        return api_result
                    LOGGER.warning("ScienceDirect API returned minimal metadata for %s; falling back", entry.link)
                except ScienceDirectApiError as exc:
                    LOGGER.warning("ScienceDirect API failed for %s: %s", entry.link or entry.entry_id, exc)

        return self._dom_enricher.enrich(record, entry)

    def _apply_api_payload(
        self,
        record: ArticleRecord,
        payload: dict[str, Any],
    ) -> tuple[ArticleRecord, int, int] | None:
        root = payload.get("full-text-retrieval-response", {})
        coredata = root.get("coredata", {})
        update: dict[str, Any] = {}

        title = _strip(coredata.get("dc:title"))
        if title and title != record.title:
            update["title"] = title

        authors = _extract_api_authors(root, coredata)
        if authors:
            update["authors"] = authors

        cover_date = _strip(coredata.get("prism:coverDate"))
        published_at = _parse_date(cover_date) if cover_date else None
        if published_at:
            update["published_at"] = published_at

        abstract = _extract_api_abstract(root, coredata)
        additional_attempts = 0
        additional_failures = 0
        if abstract and abstract != (record.abstract_original or ""):
            translation_result, attempted, language = _translate_text(self._translator, abstract)
            if attempted:
                additional_attempts = 1
                if translation_result.status == "failed":
                    additional_failures = 1
            update["abstract_original"] = abstract
            update["abstract_language"] = language
            update["abstract_zh"] = translation_result.translated_text if translation_result.translated_text else None
            update["translation"] = TranslationRecord(
                status=translation_result.status,
                translator=translation_result.translator,
                translated_at=translation_result.translated_at,
                error=translation_result.error,
            )

        if not update:
            return None
        return record.model_copy(update=update), additional_attempts, additional_failures


class _ScienceDirectDomEnricher:
    def __init__(self, translator: Translator, *, fetcher: HtmlFetcher | None = None) -> None:
        self._translator = translator
        self._fetcher: HtmlFetcher = fetcher or ScienceDirectArticleFetcher()

    def enrich(
        self,
        record: ArticleRecord,
        entry: NormalizedFeedEntry,
    ) -> tuple[ArticleRecord, int, int]:
        if not entry.link:
            return record, 0, 0
        try:
            html = self._fetcher.fetch_html(entry.link)
        except (BrowserLaunchConfigurationError, RuntimeError) as exc:
            LOGGER.warning("ScienceDirect DOM fallback skipped for %s: %s", entry.link, exc)
            return record, 0, 0
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("ScienceDirect DOM fallback failed for %s: %s", entry.link, exc)
            return record, 0, 0

        parsed = parse_sciencedirect_fallback(html, url=entry.link)
        return self._apply_parsed(record, parsed)

    def _apply_parsed(
        self,
        record: ArticleRecord,
        parsed: ScienceDirectParsedArticle,
    ) -> tuple[ArticleRecord, int, int]:
        update: dict[str, Any] = {}
        if parsed.title.value:
            update["title"] = parsed.title.value
        if parsed.authors.value:
            update["authors"] = [author.name for author in parsed.authors.value]
        if parsed.publication_date.value:
            published_at = _parse_date(parsed.publication_date.value)
            if published_at:
                update["published_at"] = published_at

        additional_attempts = 0
        additional_failures = 0
        if parsed.abstract.value and parsed.abstract.value != (record.abstract_original or ""):
            translation_result, attempted, language = _translate_text(self._translator, parsed.abstract.value)
            if attempted:
                additional_attempts = 1
                if translation_result.status == "failed":
                    additional_failures = 1
            update["abstract_original"] = parsed.abstract.value
            update["abstract_language"] = language
            update["abstract_zh"] = translation_result.translated_text if translation_result.translated_text else None
            update["translation"] = TranslationRecord(
                status=translation_result.status,
                translator=translation_result.translator,
                translated_at=translation_result.translated_at,
                error=translation_result.error,
            )

        if not update:
            return record, additional_attempts, additional_failures
        enriched = record.model_copy(update=update)
        return enriched, additional_attempts, additional_failures

    def _translate(self, text: str) -> tuple[TranslationResult, bool, str | None]:
        language = detect_language(text)
        if not text.strip():
            return skipped_translation(text), False, language
        if language and language.startswith("zh"):
            return skipped_translation(text), False, language
        result = self._translator.translate(text, source_language=language or "unknown")
        return result, True, language


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return date_parser.isoparse(value)
    except (ValueError, TypeError):
        return None


def _translate_text(translator: Translator, text: str) -> tuple[TranslationResult, bool, str | None]:
    language = detect_language(text)
    trimmed = text.strip()
    if not trimmed:
        return skipped_translation(text), False, language
    if language and language.startswith("zh"):
        return skipped_translation(text), False, language
    result = translator.translate(trimmed, source_language=language or "unknown")
    return result, True, language


def _strip(value: Any) -> str | None:
    if isinstance(value, str):
        trimmed = value.strip()
        return trimmed or None
    return None


def _extract_api_authors(root: dict[str, Any], coredata: dict[str, Any]) -> list[str]:
    authors: list[str] = []
    seen: set[str] = set()
    authors_node = root.get("authors") or coredata.get("authors")
    if isinstance(authors_node, dict):
        raw = authors_node.get("author")
        if isinstance(raw, list):
            for entry in raw:
                if not isinstance(entry, dict):
                    continue
                name = (
                    _strip(entry.get("ce:indexed-name"))
                    or _strip(entry.get("ce:surname"))
                    or _strip(entry.get("surname"))
                )
                if name and name not in seen:
                    authors.append(name)
                    seen.add(name)
    creators = coredata.get("dc:creator")
    if isinstance(creators, list):
        for creator in creators:
            if isinstance(creator, str) and creator.strip():
                trimmed = creator.strip()
                if trimmed and trimmed not in seen:
                    authors.append(trimmed)
                    seen.add(trimmed)
    elif isinstance(creators, str) and creators.strip():
        trimmed = creators.strip()
        if trimmed and trimmed not in seen:
            authors.append(trimmed)
            seen.add(trimmed)
    return authors


def _extract_api_abstract(root: dict[str, Any], coredata: dict[str, Any]) -> str | None:
    abstracts = root.get("abstracts")
    if isinstance(abstracts, dict):
        raw = abstracts.get("abstract")
        if isinstance(raw, list) and raw:
            first = raw[0]
            if isinstance(first, dict):
                paras = first.get("ce:para") or first.get("para")
                if isinstance(paras, list):
                    joined = "\n\n".join(str(p).strip() for p in paras if str(p).strip())
                    if joined:
                        return joined
                elif isinstance(paras, str) and paras.strip():
                    return paras.strip()
    description = _strip(coredata.get("dc:description"))
    if description:
        return description
    return None


def _pii_from_entry(entry: NormalizedFeedEntry) -> str | None:
    if entry.entry_id and entry.entry_id.startswith("S"):
        return entry.entry_id
    if entry.link:
        match = PII_REGEX.search(entry.link)
        if match:
            return match.group(1)
    return None
