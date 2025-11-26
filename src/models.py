from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Sequence

from pydantic import BaseModel, ConfigDict, Field

TranslationStatus = Literal["success", "failed", "skipped"]


@dataclass(frozen=True)
class JournalSource:
    name: str
    rss_url: str
    slug: str
    source_type: str
    notes: str | None = None


@dataclass(frozen=True)
class NormalizedFeedEntry:
    entry_id: str
    title: str
    summary: str
    link: str
    authors: Sequence[str]
    published_at: datetime | None


class TranslationRecord(BaseModel):
    status: TranslationStatus
    translator: str | None = None
    translated_at: datetime | None = None
    error: str | None = None

    model_config = ConfigDict(extra="forbid")


class ArticleRecord(BaseModel):
    id: str = Field(serialization_alias="id")
    title: str
    link: str
    authors: list[str]
    published_at: datetime | None = None
    abstract_original: str | None = None
    abstract_language: str | None = None
    abstract_zh: str | None = None
    translation: TranslationRecord
    fetched_at: datetime
    source: str = "RSS"

    model_config = ConfigDict(extra="forbid")


class JournalMetadata(BaseModel):
    name: str
    rss_url: str
    notes: str | None = None
    last_run_at: datetime

    model_config = ConfigDict(extra="forbid")


class JournalArchive(BaseModel):
    journal: JournalMetadata
    entries: list[ArticleRecord]

    model_config = ConfigDict(extra="forbid")
