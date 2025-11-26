"""
英文导入入口：封装 3_translation 包。
"""

from __future__ import annotations

from typing import Any, cast

from econatlas._loader import load_local_module

_base = cast(Any, load_local_module(__file__, "3_translation/3.1_翻译基础.py", "econatlas._trans_base"))
_deepseek = cast(Any, load_local_module(__file__, "3_translation/3.2_DeepSeek_翻译.py", "econatlas._trans_ds"))

TranslationResult = _base.TranslationResult
Translator = _base.Translator
detect_language = _base.detect_language
skipped_translation = _base.skipped_translation
failed_translation = _base.failed_translation
NoOpTranslator = _base.NoOpTranslator

DeepSeekTranslator = _deepseek.DeepSeekTranslator

__all__ = [
    "TranslationResult",
    "Translator",
    "detect_language",
    "skipped_translation",
    "failed_translation",
    "NoOpTranslator",
    "DeepSeekTranslator",
]
