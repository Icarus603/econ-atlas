"""
英文导入入口：封装 4_storage 包。
"""

from __future__ import annotations

from typing import Any, cast

from econatlas._loader import load_local_module

_store = cast(Any, load_local_module(__file__, "4_storage/4.1_JSON存储.py", "econatlas._storage_json"))

JournalStore = _store.JournalStore
StorageResult = _store.StorageResult

__all__ = ["JournalStore", "StorageResult"]
