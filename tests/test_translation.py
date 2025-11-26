from __future__ import annotations

from econatlas.translation import detect_language, skipped_translation, TranslationResult


def test_detect_language_handles_empty() -> None:
    assert detect_language("") is None
    assert detect_language("    ") is None


def test_skipped_translation_returns_same_text() -> None:
    text = "hello"
    result = skipped_translation(text)
    assert isinstance(result, TranslationResult)
    assert result.status == "skipped"
    assert result.translated_text == text
