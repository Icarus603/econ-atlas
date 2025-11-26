from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping, Sequence


@dataclass(frozen=True, slots=True)
class JournalInventory:
    """Inventory metadata for a single journal slug."""

    slug: str
    sample_count: int
    latest_fetched_at: datetime | None

    def to_dict(self) -> dict[str, object]:
        return {
            "slug": self.slug,
            "sample_count": self.sample_count,
            "latest_fetched_at": self.latest_fetched_at.isoformat() if self.latest_fetched_at else None,
        }


@dataclass(frozen=True, slots=True)
class SourceInventory:
    """Aggregated inventory for a given source type."""

    source_type: str
    total_samples: int
    latest_fetched_at: datetime | None
    notes: str | None
    journals: Sequence[JournalInventory]

    def to_dict(self) -> dict[str, object]:
        return {
            "source_type": self.source_type,
            "total_samples": self.total_samples,
            "latest_fetched_at": self.latest_fetched_at.isoformat() if self.latest_fetched_at else None,
            "notes": self.notes,
            "journals": [journal.to_dict() for journal in self.journals],
        }


DEFAULT_SOURCE_NOTES: dict[str, str] = {
    "chicago": "RSS feed returns 403 without a fresh Cloudflare session cookie captured from the browser.",
    "informs": "RSS endpoint requires Cloudflare clearance cookies; capture them via browser developer tools.",
    "nber": "JSON feed entries include relative links; prefix https://www.nber.org before fetching article HTML.",
}


def build_inventory(samples_dir: Path, extra_notes: Mapping[str, str] | None = None) -> list[SourceInventory]:
    """Scan the samples directory and build per-source inventory data."""
    notes = {**DEFAULT_SOURCE_NOTES, **(extra_notes or {})}
    if not samples_dir.exists():
        return []

    inventories: list[SourceInventory] = []
    for source_dir in sorted(child for child in samples_dir.iterdir() if child.is_dir()):
        journals = _collect_journal_data(source_dir)
        total_samples = sum(journal.sample_count for journal in journals)
        latest = _latest_datetime(journal.latest_fetched_at for journal in journals if journal.latest_fetched_at)
        inventories.append(
            SourceInventory(
                source_type=source_dir.name,
                total_samples=total_samples,
                latest_fetched_at=latest,
                notes=notes.get(source_dir.name),
                journals=journals,
            )
        )
    return inventories


def _collect_journal_data(source_dir: Path) -> list[JournalInventory]:
    journal_dirs = sorted(child for child in source_dir.iterdir() if child.is_dir())
    journals: list[JournalInventory] = []
    if not journal_dirs:
        journals.append(JournalInventory(slug="(none)", sample_count=0, latest_fetched_at=None))
        return journals

    for journal_dir in journal_dirs:
        files = sorted(journal_dir.glob("*.html"))
        sample_count = len(files)
        latest = _latest_datetime(
            datetime.fromtimestamp(file.stat().st_mtime, tz=timezone.utc) for file in files
        )
        journals.append(
            JournalInventory(
                slug=journal_dir.name,
                sample_count=sample_count,
                latest_fetched_at=latest,
            )
        )
    return journals


def _latest_datetime(values: Iterable[datetime]) -> datetime | None:
    latest_value: datetime | None = None
    for value in values:
        if latest_value is None or value > latest_value:
            latest_value = value
    return latest_value
