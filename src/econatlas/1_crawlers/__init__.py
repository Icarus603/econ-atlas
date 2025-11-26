"""
爬虫层：仅暴露按出版商划分的爬虫。
"""

from __future__ import annotations

from econatlas._loader import load_local_module

_cnki = load_local_module(__file__, "1.0_CNKI_爬虫.py", "econatlas._crawler_cnki")
_scd = load_local_module(__file__, "1.1_ScienceDirect_爬虫.py", "econatlas._crawler_scd")
_oxford = load_local_module(__file__, "1.2_Oxford_爬虫.py", "econatlas._crawler_oxford")
_cambridge = load_local_module(__file__, "1.3_Cambridge_爬虫.py", "econatlas._crawler_cambridge")

CNKI爬虫 = _cnki.CNKI爬虫  # type: ignore[attr-defined]
ScienceDirect爬虫 = _scd.ScienceDirect爬虫  # type: ignore[attr-defined]
Oxford爬虫 = _oxford.Oxford爬虫  # type: ignore[attr-defined]
Cambridge爬虫 = _cambridge.Cambridge爬虫  # type: ignore[attr-defined]

__all__ = [
    "ScienceDirect爬虫",
    "CNKI爬虫",
    "Oxford爬虫",
    "Cambridge爬虫",
]
