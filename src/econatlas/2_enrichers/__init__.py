"""
出版商增强器集合：ScienceDirect API、Oxford 作者补全等。
"""

from __future__ import annotations

from econatlas._loader import load_local_module

_scd = load_local_module(__file__, "2.1_ScienceDirect_增强器.py", "econatlas._enricher_scd")
_oxford = load_local_module(__file__, "2.2_Oxford_增强器.py", "econatlas._enricher_oxford")

ScienceDirectEnricher = _scd.ScienceDirectEnricher
ScienceDirectApiClient = _scd.ScienceDirectApiClient
ElsevierApiConfig = _scd.ElsevierApiConfig
ScienceDirectApiError = _scd.ScienceDirectApiError

OxfordEnricher = _oxford.OxfordEnricher
OxfordArticleFetcher = _oxford.OxfordArticleFetcher
PersistentOxfordSession = _oxford.PersistentOxfordSession

__all__ = [
    "ScienceDirectEnricher",
    "ScienceDirectApiClient",
    "ElsevierApiConfig",
    "ScienceDirectApiError",
    "OxfordEnricher",
    "OxfordArticleFetcher",
    "PersistentOxfordSession",
]
