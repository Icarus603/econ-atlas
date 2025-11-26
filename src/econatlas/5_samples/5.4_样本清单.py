"""
样本清单：遍历样本目录，统计每个来源和期刊的 HTML 样本数量与时间。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping, Sequence


@dataclass(frozen=True, slots=True)
class JournalInventory:
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
    "chicago": "RSS 需要最新的 Cloudflare 会话 cookie。",
    "informs": "RSS 需要 Cloudflare clearance cookies，从浏览器开发者工具获取。",
    "nber": "JSON feed 使用相对链接，需要补上 https://www.nber.org。",
}


def build_inventory(samples_dir: Path, extra_notes: Mapping[str, str] | None = None) -> list[SourceInventory]:
    """扫描样本目录并生成汇总。"""
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
