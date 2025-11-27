"""
英文导入入口：封装 1_crawlers 下的按出版商爬虫。
"""

from __future__ import annotations

from typing import Any, cast

from econatlas._loader import load_local_module

_cnki = cast(Any, load_local_module(__file__, "1_crawlers/1.0_CNKI_爬虫.py", "econatlas._crawler_cnki"))
_scd = cast(Any, load_local_module(__file__, "1_crawlers/1.1_ScienceDirect_爬虫.py", "econatlas._crawler_scd"))
_oxford = cast(Any, load_local_module(__file__, "1_crawlers/1.2_Oxford_爬虫.py", "econatlas._crawler_oxford"))
_cambridge = cast(Any, load_local_module(__file__, "1_crawlers/1.3_Cambridge_爬虫.py", "econatlas._crawler_cambridge"))
_nber = cast(Any, load_local_module(__file__, "1_crawlers/1.4_NBER_爬虫.py", "econatlas._crawler_nber"))
_wiley = cast(Any, load_local_module(__file__, "1_crawlers/1.5_Wiley_爬虫.py", "econatlas._crawler_wiley"))
_chicago = cast(Any, load_local_module(__file__, "1_crawlers/1.6_Chicago_爬虫.py", "econatlas._crawler_chicago"))
_informs = cast(Any, load_local_module(__file__, "1_crawlers/1.7_Informs_爬虫.py", "econatlas._crawler_informs"))

CNKI爬虫 = _cnki.CNKI爬虫
ScienceDirect爬虫 = _scd.ScienceDirect爬虫
Oxford爬虫 = _oxford.Oxford爬虫
Cambridge爬虫 = _cambridge.Cambridge爬虫
NBER爬虫 = _nber.NBER爬虫
Wiley爬虫 = _wiley.Wiley爬虫
Chicago爬虫 = _chicago.Chicago爬虫
Informs爬虫 = _informs.Informs爬虫

__all__ = [
    "ScienceDirect爬虫",
    "CNKI爬虫",
    "Oxford爬虫",
    "Cambridge爬虫",
    "NBER爬虫",
    "Wiley爬虫",
    "Chicago爬虫",
    "Informs爬虫",
]
