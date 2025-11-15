from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

from econ_atlas.models import ArticleRecord, JournalArchive, JournalMetadata, JournalSource, TranslationRecord

LOGGER = logging.getLogger(__name__)


@dataclass
class StorageResult:
    added: int = 0
    updated: int = 0


class JournalStore:
    """Manages per-journal JSON archives."""

    def __init__(self, output_dir: Path):
        self._output_dir = output_dir
        self._output_dir.mkdir(parents=True, exist_ok=True)

    def persist(self, journal: JournalSource, entries: list[ArticleRecord]) -> StorageResult:
        archive = self._load_archive(journal)
        by_id: Dict[str, ArticleRecord] = {entry.id: entry for entry in archive.entries}
        added = 0
        updated = 0

        for entry in entries:
            existing = by_id.get(entry.id)
            if existing is None:
                by_id[entry.id] = entry
                added += 1
                continue
            merged = _merge_entries(existing, entry)
            if merged != existing:
                by_id[entry.id] = merged
                updated += 1

        sorted_entries = sorted(
            by_id.values(),
            key=lambda e: (e.published_at or e.fetched_at),
        )
        archive.entries = sorted_entries
        archive.journal = JournalMetadata(
            name=journal.name,
            rss_url=journal.rss_url,
            notes=journal.notes,
            last_run_at=datetime.now(timezone.utc),
        )
        self._write_archive(journal, archive)
        return StorageResult(added=added, updated=updated)

    def _load_archive(self, journal: JournalSource) -> JournalArchive:
        path = self._path_for(journal)
        if not path.exists():
            return JournalArchive(
                journal=JournalMetadata(
                    name=journal.name,
                    rss_url=journal.rss_url,
                    notes=journal.notes,
                    last_run_at=datetime.now(timezone.utc),
                ),
                entries=[],
            )
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return JournalArchive.model_validate(data)
        except Exception as exc:  # noqa: BLE001
            LOGGER.error("Failed to read %s: %s", path, exc)
            raise

    def _write_archive(self, journal: JournalSource, archive: JournalArchive) -> None:
        path = self._path_for(journal)
        payload = archive.model_dump(mode="json")
        payload_str = json.dumps(payload, ensure_ascii=False, indent=2)
        tmp_path = path.with_suffix(".tmp")
        tmp_path.write_text(payload_str, encoding="utf-8")
        os.replace(tmp_path, path)

    def _path_for(self, journal: JournalSource) -> Path:
        return self._output_dir / f"{journal.slug}.json"


def _merge_entries(existing: ArticleRecord, new_entry: ArticleRecord) -> ArticleRecord:
    abstract_zh = existing.abstract_zh or new_entry.abstract_zh
    translation = _prefer_translation(existing.translation, new_entry.translation)
    # Pydantic models are immutable by default; use model_copy/update.
    return existing.model_copy(
        update={
            "abstract_original": existing.abstract_original or new_entry.abstract_original,
            "abstract_language": existing.abstract_language or new_entry.abstract_language,
            "abstract_zh": abstract_zh,
            "translation": translation,
            "authors": existing.authors or new_entry.authors,
            "published_at": existing.published_at or new_entry.published_at,
            "link": existing.link or new_entry.link,
            "title": existing.title or new_entry.title,
        }
    )


def _prefer_translation(old: TranslationRecord, new: TranslationRecord) -> TranslationRecord:
    if old.status == "success":
        return old
    if new.status == "success":
        return new
    if old.status == "failed" and new.status == "failed":
        # Keep the newer failure reason
        return new
    return old
