"""
DeepSeek 翻译适配器：调用官方 API 翻译摘要。
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

import httpx

from econatlas._loader import load_local_module

_base = load_local_module(__file__, "3.1_翻译基础.py", "econatlas._trans_base")
TranslationResult = _base.TranslationResult  # type: ignore[attr-defined]
Translator = _base.Translator  # type: ignore[attr-defined]

LOGGER = logging.getLogger(__name__)

DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"


class DeepSeekTranslator(Translator):
    """基于 DeepSeek 的翻译实现。"""

    def __init__(
        self,
        api_key: str,
        *,
        model: str = "deepseek-chat",
        timeout: float = 30.0,
        max_retries: int = 5,
        backoff_seconds: float = 1.0,
    ):
        self._api_key = api_key
        self._model = model
        self._timeout = timeout
        self._max_retries = max(1, max_retries)
        self._backoff_seconds = backoff_seconds

    def translate(self, text: str, *, source_language: str | None = None, target_language: str = "zh") -> TranslationResult:
        if not text.strip():
            return TranslationResult(
                status="skipped",
                translated_text="",
                translator="deepseek",
                translated_at=datetime.now(timezone.utc),
            )

        payload = {
            "model": self._model,
            "temperature": 0.2,
            "messages": [
                {
                    "role": "system",
                    "content": "You translate academic abstracts into fluent, formal Simplified Chinese while preserving terminology.",
                },
                {
                    "role": "user",
                    "content": (
                        f"Source language: {source_language or 'unknown'}\n"
                        f"Target language: {target_language}\n"
                        "Translate the following abstract:\n"
                        f"{text}"
                    ),
                },
            ],
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        data: dict[str, object] | None = None
        for attempt in range(1, self._max_retries + 1):
            try:
                response = httpx.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=self._timeout)
                response.raise_for_status()
                data = response.json()
                break
            except httpx.HTTPError as exc:
                LOGGER.error("DeepSeek 请求失败: %s (attempt %s/%s)", exc, attempt, self._max_retries)
                if attempt == self._max_retries:
                    return TranslationResult(
                        status="failed",
                        translated_text=None,
                        translator="deepseek",
                        translated_at=datetime.now(timezone.utc),
                        error=str(exc),
                    )
                time.sleep(self._backoff_seconds * attempt)
        if data is None:
            return TranslationResult(
                status="failed",
                translated_text=None,
                translator="deepseek",
                translated_at=datetime.now(timezone.utc),
                error="empty response",
            )

        message = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()
        )
        if not message:
            LOGGER.error("DeepSeek 返回空内容: %s", data)
            return TranslationResult(
                status="failed",
                translated_text=None,
                translator="deepseek",
                translated_at=datetime.now(timezone.utc),
                error="empty response",
            )

        return TranslationResult(
            status="success",
            translated_text=message,
            translator="deepseek",
            translated_at=datetime.now(timezone.utc),
        )
