from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any

from dateutil import parser as date_parser

from econ_atlas.models import ArticleRecord, NormalizedFeedEntry, TranslationRecord
from econ_atlas.sources.sciencedirect_api import ScienceDirectApiClient, ScienceDirectApiError
from econ_atlas.translate.base import NoOpTranslator, TranslationResult, Translator, detect_language, skipped_translation

LOGGER = logging.getLogger(__name__)
PII_REGEX = re.compile(r"/pii/([^/?#]+)", re.IGNORECASE)


class ScienceDirectEnricher:
    """Elsevier API-based enricher for ScienceDirect."""

    def __init__(
        self,
        translator: Translator,
        *,
        api_client: ScienceDirectApiClient | None = None,
    ) -> None:
        self._translator = translator
        self._api_client = api_client
        self._logged_missing_client = False

    def enrich(
        self,
        record: ArticleRecord,
        entry: NormalizedFeedEntry,
    ) -> tuple[ArticleRecord, int, int]:
        if self._api_client is None:
            if not self._logged_missing_client:
                LOGGER.warning("ScienceDirect API client missing; skipping enrichment for %s", entry.link or entry.entry_id)
                self._logged_missing_client = True
            return record, 0, 0

        pii = _pii_from_entry(entry)
        if not pii:
            LOGGER.warning("ScienceDirect entry missing PII; skipping enrichment for %s", entry.link or entry.entry_id)
            return record, 0, 0

        try:
            payload = self._api_client.fetch_by_pii(pii)
            api_result = self._apply_api_payload(record, payload)
            if api_result is not None:
                return api_result
            LOGGER.warning("ScienceDirect API returned minimal metadata for %s", entry.link or entry.entry_id)
        except ScienceDirectApiError as exc:
            LOGGER.warning("ScienceDirect API failed for %s: %s", entry.link or entry.entry_id, exc)

        return record, 0, 0

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
    if isinstance(translator, NoOpTranslator):
        return translator.translate(trimmed, source_language=language or "unknown"), False, language
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

    def _append(name: str | None) -> None:
        if name and name not in seen:
            authors.append(name)
            seen.add(name)

    def _name_from_author(entry: Any) -> str | None:
        if isinstance(entry, str):
            return entry.strip() or None
        if isinstance(entry, dict):
            for key in ("ce:indexed-name", "ce:surname", "surname"):
                candidate = _strip(entry.get(key))
                if candidate:
                    return candidate
            for key in ("$", "#text"):
                value = entry.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        return None

    if isinstance(authors_node, dict):
        raw = authors_node.get("author")
        if isinstance(raw, list):
            for entry in raw:
                _append(_name_from_author(entry))
        elif raw is not None:
            _append(_name_from_author(raw))

    creators = coredata.get("dc:creator")
    if isinstance(creators, list):
        for creator in creators:
            _append(_name_from_author(creator))
    elif creators is not None:
        _append(_name_from_author(creators))
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
