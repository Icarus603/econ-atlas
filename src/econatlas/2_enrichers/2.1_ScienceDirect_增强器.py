"""
ScienceDirect 增强器：使用 Elsevier API 拉取元数据并翻译摘要。
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, cast

import httpx
from dateutil import parser as date_parser

from econatlas.models import ArticleRecord, NormalizedFeedEntry
from econatlas.translation import detect_language

LOGGER = logging.getLogger(__name__)
PII_REGEX = re.compile(r"/pii/([^/?#]+)", re.IGNORECASE)
DEFAULT_BASE_URL = "https://api.elsevier.com/content/article/pii/"


class ScienceDirectApiError(RuntimeError):
    """Elsevier API 调用失败时抛出。"""

    def __init__(self, message: str, *, recoverable: bool = False):
        super().__init__(message)
        self.recoverable = recoverable


@dataclass(frozen=True)
class ElsevierApiConfig:
    api_key: str
    inst_token: str | None = None
    base_url: str = DEFAULT_BASE_URL
    timeout: float = 15.0
    max_retries: int = 5
    backoff_seconds: float = 1.0


class ScienceDirectApiClient:
    """Elsevier Article Retrieval API 轻量封装。"""

    def __init__(self, config: ElsevierApiConfig) -> None:
        self._config = config
        self._client = httpx.Client(timeout=config.timeout)

    def close(self) -> None:
        self._client.close()

    def fetch_by_pii(self, pii: str) -> dict[str, Any]:
        url = self._config.base_url.rstrip("/") + "/" + pii
        headers = self._build_headers()
        params = {"httpAccept": "application/json"}
        for attempt in range(1, self._config.max_retries + 1):
            try:
                response = self._client.get(url, headers=headers, params=params)
            except httpx.HTTPError as exc:
                delay = min(self._config.backoff_seconds * (2 ** (attempt - 1)), 30)
                LOGGER.warning("Elsevier API 连接失败 %s (attempt %s/%s); %.1fs 后重试", exc, attempt, self._config.max_retries, delay)
                if attempt == self._config.max_retries:
                    raise ScienceDirectApiError(f"Elsevier API 连接失败: {exc}", recoverable=True) from exc
                time.sleep(delay)
                continue
            if response.status_code == 200:
                return cast(dict[str, Any], response.json())
            if response.status_code in {401, 403}:
                raise ScienceDirectApiError("Elsevier API 拒绝请求，请检查 API key/insttoken")
            if response.status_code == 404:
                raise ScienceDirectApiError("ScienceDirect PII 不存在")
            if response.status_code == 429 or response.status_code >= 500:
                delay = min(self._config.backoff_seconds * (2 ** (attempt - 1)), 30)
                LOGGER.warning("Elsevier API %s %s; %.1fs 后重试", response.status_code, response.text[:120], delay)
                time.sleep(delay)
                continue
            raise ScienceDirectApiError(
                f"Elsevier API 错误 {response.status_code}: {response.text[:200]}", recoverable=False
            )
        raise ScienceDirectApiError("Elsevier API 重试耗尽", recoverable=True)

    def _build_headers(self) -> dict[str, str]:
        headers = {
            "X-ELS-APIKey": self._config.api_key,
            "Accept": "application/json",
        }
        if self._config.inst_token:
            headers["X-ELS-Insttoken"] = self._config.inst_token
        return headers


class ScienceDirectEnricher:
    """使用 Elsevier API 为 ScienceDirect 条目补充信息（不负责翻译）。"""

    def __init__(
        self,
        *,
        api_client: ScienceDirectApiClient | None = None,
    ) -> None:
        self._api_client = api_client
        self._logged_missing_client = False

    def enrich(
        self,
        record: ArticleRecord,
        entry: NormalizedFeedEntry,
    ) -> tuple[ArticleRecord, bool]:
        if self._api_client is None:
            if not self._logged_missing_client:
                LOGGER.warning("缺少 ScienceDirect API client，跳过增强：%s", entry.link or entry.entry_id)
                self._logged_missing_client = True
            return record, True

        pii = _pii_from_entry(entry)
        if not pii:
            LOGGER.warning("ScienceDirect entry 缺少 PII，跳过：%s", entry.link or entry.entry_id)
            return record, True

        try:
            payload = self._api_client.fetch_by_pii(pii)
            api_result = self._apply_api_payload(record, payload)
            if api_result is not None:
                enriched_record, added, updated = api_result
                _ = (added, updated)  # 保留原返回结构
                return enriched_record, True
            LOGGER.warning("ScienceDirect API 返回信息不足：%s", entry.link or entry.entry_id)
        except ScienceDirectApiError as exc:
            LOGGER.warning("ScienceDirect API 调用失败 %s: %s", entry.link or entry.entry_id, exc)

        return record, False

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
        if abstract and abstract != (record.abstract_original or ""):
            update["abstract_original"] = abstract
            update["abstract_language"] = detect_language(abstract)

        if not update:
            return None
        return record.model_copy(update=update), 0, 0


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return date_parser.isoparse(value)
    except (ValueError, TypeError):
        return None


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
