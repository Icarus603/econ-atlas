"""
期刊列表加载：从 CSV 读取期刊元数据并生成 slug。
"""

from __future__ import annotations

import csv
import logging
from collections import Counter
from pathlib import Path
from typing import Iterable

from slugify import slugify

from econatlas.models import JournalSource

LOGGER = logging.getLogger(__name__)

NAME_KEYS = ("期刊名称", "名称", "name", "journal")
RSS_KEYS = ("RSS链接", "RSS链接（中文直接在知网上复制RSS链接）", "rss")
NOTES_KEYS = ("备注", "notes")
SOURCE_KEYS = ("source_type", "来源", "publisher", "source")
ALLOWED_SOURCE_TYPES = {
    "cnki",
    "wiley",
    "oxford",
    "cambridge",
    "sciencedirect",
    "chicago",
    "informs",
    "nber",
}


class JournalListLoader:
    """从 list.csv 读取期刊列表。"""

    def __init__(self, csv_path: Path):
        self._csv_path = csv_path

    def load(self) -> list[JournalSource]:
        journals: list[JournalSource] = []
        slug_counts: Counter[str] = Counter()
        with self._csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames:
                LOGGER.warning("CSV %s 无表头", self._csv_path)
                return journals
            for index, row in enumerate(reader, start=1):
                name = _extract_value(row, NAME_KEYS)
                rss_url = _extract_value(row, RSS_KEYS)
                notes = _extract_value(row, NOTES_KEYS) or None

                if not name:
                    LOGGER.debug("跳过行 %s：缺少期刊名", index)
                    continue
                if not rss_url:
                    LOGGER.warning("跳过 %s (行 %s)：缺少 RSS", name, index)
                    continue

                source_type_value = _extract_value(row, SOURCE_KEYS)
                normalized_source = _normalize_source_type(source_type_value)
                if not normalized_source:
                    LOGGER.warning("跳过 %s (行 %s)：非法 source_type '%s'", name, index, source_type_value)
                    continue

                slug = _unique_slug(name, slug_counts)
                journals.append(
                    JournalSource(
                        name=name,
                        rss_url=rss_url,
                        slug=slug,
                        source_type=normalized_source,
                        notes=notes,
                    )
                )
        return journals


def _extract_value(row: dict[str, str], preferred_keys: Iterable[str]) -> str:
    for key in preferred_keys:
        if key in row and row[key]:
            value = row[key].strip()
            if value:
                return value

    lowered = {key.lower(): value for key, value in row.items() if value}
    for key in preferred_keys:
        lowered_value = lowered.get(key.lower())
        if lowered_value:
            return lowered_value.strip()
    for key, value in row.items():
        if not value:
            continue
        if any(fragment.lower() in key.lower() for fragment in preferred_keys):
            trimmed = value.strip()
            if trimmed:
                return trimmed
    return ""


def _unique_slug(name: str, counter: Counter[str]) -> str:
    base = slugify(name, lowercase=True, separator="-")
    if not base:
        base = "journal"
    counter[base] += 1
    if counter[base] == 1:
        return base
    return f"{base}-{counter[base]}"


def _normalize_source_type(value: str) -> str:
    if not value:
        return ""
    normalized = value.strip().lower()
    if normalized in ALLOWED_SOURCE_TYPES:
        return normalized
    return ""
