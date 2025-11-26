from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx

from econ_atlas.translate.base import TranslationResult, Translator

LOGGER = logging.getLogger(__name__)

DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"


class DeepSeekTranslator(Translator):
    """LLM-backed translator that calls the DeepSeek API."""

    def __init__(self, api_key: str, *, model: str = "deepseek-chat", timeout: float = 30.0):
        self._api_key = api_key
        self._model = model
        self._timeout = timeout

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
        try:
            response = httpx.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=self._timeout)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPError as exc:
            LOGGER.error("DeepSeek request failed: %s", exc)
            return TranslationResult(
                status="failed",
                translated_text=None,
                translator="deepseek",
                translated_at=datetime.now(timezone.utc),
                error=str(exc),
            )

        message = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()
        )
        if not message:
            LOGGER.error("DeepSeek returned empty content: %s", data)
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
