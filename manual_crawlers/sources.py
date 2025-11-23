from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class ManualSource:
    key: str
    name: str
    slug: str
    env_cookie_var: str
    notes: str


SOURCES: Dict[str, ManualSource] = {
    "economic-history-review": ManualSource(
        key="economic-history-review",
        name="Economic History Review",
        slug="economic-history-review",
        env_cookie_var="WILEY_COOKIES",
        notes="Wiley",
    ),
    "international-economic-review": ManualSource(
        key="international-economic-review",
        name="International Economic Review",
        slug="international-economic-review",
        env_cookie_var="WILEY_COOKIES",
        notes="Wiley",
    ),
    "journal-of-accounting-research": ManualSource(
        key="journal-of-accounting-research",
        name="Journal of Accounting Research",
        slug="journal-of-accounting-research",
        env_cookie_var="WILEY_COOKIES",
        notes="Wiley",
    ),
    "journal-of-political-economy": ManualSource(
        key="journal-of-political-economy",
        name="Journal of Political Economy",
        slug="journal-of-political-economy",
        env_cookie_var="CHICAGO_COOKIES",
        notes="Chicago",
    ),
    "management-science": ManualSource(
        key="management-science",
        name="Management Science",
        slug="management-science",
        env_cookie_var="INFORMS_COOKIES",
        notes="INFORMS",
    ),
    "strategic-management-journal": ManualSource(
        key="strategic-management-journal",
        name="Strategic Management Journal",
        slug="strategic-management-journal",
        env_cookie_var="WILEY_COOKIES",
        notes="Wiley",
    ),
}


def list_source_keys() -> List[str]:
    return list(SOURCES.keys())
