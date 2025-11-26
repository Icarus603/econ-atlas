"""
翻译基类与语言检测。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol, cast

from langdetect import DetectorFactory, LangDetectException, detect

from econatlas.models import TranslationStatus

DetectorFactory.seed = 0


def detect_language(text: str) -> str | None:
    """检测文本语言代码。"""
    trimmed = text.strip()
    if not trimmed:
        return None
    try:
        return cast(str, detect(trimmed))
    except LangDetectException:
        return None


@dataclass(frozen=True)
class TranslationResult:
    status: TranslationStatus
    translated_text: str | None
    translator: str | None
    translated_at: datetime | None
    error: str | None = None


class Translator(Protocol):
    """翻译器协议。"""

    def translate(self, text: str, *, source_language: str | None = None, target_language: str = "zh") -> TranslationResult:
        ...


def skipped_translation(text: str) -> TranslationResult:
    now = datetime.now(timezone.utc)
    return TranslationResult(
        status="skipped",
        translated_text=text,
        translator=None,
        translated_at=now,
    )


def failed_translation(error: str) -> TranslationResult:
    now = datetime.now(timezone.utc)
    return TranslationResult(
        status="failed",
        translated_text=None,
        translator="deepseek",
        translated_at=now,
        error=error,
    )


class NoOpTranslator(Translator):
    """禁用翻译的占位实现。"""

    def translate(
        self,
        text: str,
        *,
        source_language: str | None = None,
        target_language: str = "zh",
    ) -> TranslationResult:
        now = datetime.now(timezone.utc)
        return TranslationResult(
            status="skipped",
            translated_text=None,
            translator=None,
            translated_at=now,
        )
