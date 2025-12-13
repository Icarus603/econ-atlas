from __future__ import annotations

from datetime import datetime
from typing import List

from econatlas.models import NormalizedFeedEntry, JournalSource
from econatlas.crawlers import CNKI爬虫


class FakeFeedClient:
    def __init__(self, entries: List[NormalizedFeedEntry]) -> None:
        self._entries = entries

    def fetch(self, rss_url: str) -> List[NormalizedFeedEntry]:
        return self._entries


def test_cnki_crawler_builds_records() -> None:
    entry = NormalizedFeedEntry(
        entry_id="1",
        title="A &amp; B",
        summary="hello world",
        link="https://kns.cnki.net/kcms2/article/abstract?v=abc&uniplatform=NZKPT&language=CHS",
        authors=("a",),
        published_at=datetime(2024, 1, 1),
    )
    crawler = CNKI爬虫(FakeFeedClient([entry]))
    journal = JournalSource(name="J", rss_url="http://rss", slug="j", source_type="cnki")
    records = crawler.crawl(journal)
    assert len(records) == 1
    rec = records[0]
    assert rec.id == "1"
    assert rec.link.startswith("https://kns.cnki.net/kns8/defaultresult/index?kw=")
    assert rec.link.endswith("A+%26+B")
    assert rec.abstract_original == "hello world"
    assert rec.translation.status == "skipped"
