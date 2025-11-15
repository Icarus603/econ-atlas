from __future__ import annotations

import csv
import logging
from collections import Counter
from pathlib import Path
from typing import Iterable

from slugify import slugify

from econ_atlas.models import JournalSource

LOGGER = logging.getLogger(__name__)

NAME_KEYS = ("期刊名称", "名称", "name", "journal")
RSS_KEYS = ("RSS链接", "RSS链接（中文直接在知网上复制RSS链接）", "rss")
NOTES_KEYS = ("备注", "notes")


class JournalListLoader:
    """Loads journal metadata from list.csv."""

    def __init__(self, csv_path: Path):
        self._csv_path = csv_path

    def load(self) -> list[JournalSource]:
        journals: list[JournalSource] = []
        slug_counts: Counter[str] = Counter()
        with self._csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames:
                LOGGER.warning("CSV %s has no header", self._csv_path)
                return journals
            for index, row in enumerate(reader, start=1):
                name = _extract_value(row, NAME_KEYS)
                rss_url = _extract_value(row, RSS_KEYS)
                notes = _extract_value(row, NOTES_KEYS) or None

                if not name:
                    LOGGER.debug("Skipping row %s without a journal name", index)
                    continue
                if not rss_url:
                    LOGGER.warning("Skipping %s (row %s) because RSS is missing", name, index)
                    continue

                slug = _unique_slug(name, slug_counts)
                journals.append(JournalSource(name=name, rss_url=rss_url, slug=slug, notes=notes))
        return journals


def _extract_value(row: dict[str, str], preferred_keys: Iterable[str]) -> str:
    """Extract a trimmed CSV value by trying preferred keys, then fuzzy matches."""
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
