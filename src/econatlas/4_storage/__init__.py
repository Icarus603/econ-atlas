"""
存储层导出：JSON 持久化。
"""

from __future__ import annotations

from econatlas._loader import load_local_module

_json_store = load_local_module(__file__, "4.1_JSON存储.py", "econatlas._storage_json")

JournalStore = _json_store.JournalStore
StorageResult = _json_store.StorageResult

__all__ = ["JournalStore", "StorageResult"]
