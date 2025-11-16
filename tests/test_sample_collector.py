from datetime import datetime, timezone
from pathlib import Path

from econ_atlas.models import JournalSource, NormalizedFeedEntry
from econ_atlas.source_profiling.sample_collector import (
    JournalSampleReport,
    SampleCollector,
    _build_fetch_request,
)


class StubFeedClient:
    def __init__(self, entries_map: dict[str, list[NormalizedFeedEntry]]):
        self._entries_map = entries_map

    def fetch(self, rss_url: str) -> list[NormalizedFeedEntry]:
        if rss_url not in self._entries_map:
            raise RuntimeError("no feed")
        return self._entries_map[rss_url]


def _entry(entry_id: str, link: str) -> NormalizedFeedEntry:
    return NormalizedFeedEntry(
        entry_id=entry_id,
        title=f"Title {entry_id}",
        summary="",
        link=link,
        authors=[],
        published_at=datetime.now(timezone.utc),
    )


def test_sample_collector_saves_files(tmp_path: Path) -> None:
    journal = JournalSource(
        name="Journal",
        rss_url="https://example.com/rss",
        slug="journal",
        source_type="wiley",
    )
    entries = [_entry("id-1", "https://example.com/one"), _entry("id-2", "https://example.com/two")]
    feed_client = StubFeedClient({"https://example.com/rss": entries})
    payloads = {
        "https://example.com/one": b"<html>one</html>",
        "https://example.com/two": b"<html>two</html>",
    }

    def fake_fetch_html(
        url: str,
        headers: dict[str, str] | None = None,
        cookies: dict[str, str] | None = None,
    ) -> bytes:
        assert headers
        return payloads[url]

    collector = SampleCollector(feed_client=feed_client, fetch_html=fake_fetch_html)
    report = collector.collect([journal], limit_per_journal=5, output_dir=tmp_path)

    assert report.total_saved == 2
    saved_dir = tmp_path / "wiley" / "journal"
    assert (saved_dir / "id-1.html").read_bytes() == b"<html>one</html>"
    assert (saved_dir / "id-2.html").read_bytes() == b"<html>two</html>"
    assert not report.failures


def test_sample_collector_records_errors(tmp_path: Path) -> None:
    journal = JournalSource(
        name="Journal",
        rss_url="https://example.com/rss",
        slug="journal",
        source_type="wiley",
    )
    entries = [_entry("id-1", "https://example.com/one")]
    feed_client = StubFeedClient({"https://example.com/rss": entries})

    def failing_fetch_html(
        url: str,
        headers: dict[str, str] | None = None,
        cookies: dict[str, str] | None = None,
    ) -> bytes:
        raise RuntimeError("boom")

    collector = SampleCollector(feed_client=feed_client, fetch_html=failing_fetch_html)
    report = collector.collect([journal], limit_per_journal=1, output_dir=tmp_path)

    assert report.total_saved == 0
    assert report.failures
    failure: JournalSampleReport = report.results[0]
    assert "boom" in failure.errors[0]


def test_build_fetch_request_wiley() -> None:
    journal = JournalSource(
        name="Journal",
        rss_url="https://example.com/rss",
        slug="journal",
        source_type="wiley",
    )
    entry = _entry("id-1", "https://onlinelibrary.wiley.com/doi/10.1111/ehr.70000?af=R")
    request = _build_fetch_request(journal, entry)
    assert request.url == "https://onlinelibrary.wiley.com/doi/abs/10.1111/ehr.70000"
    assert request.headers["Referer"] == "https://onlinelibrary.wiley.com/doi/recent"


def test_build_fetch_request_cambridge_follow_redirect() -> None:
    journal = JournalSource(
        name="Journal",
        rss_url="https://example.com/rss",
        slug="journal",
        source_type="cambridge",
    )
    entry = _entry("id-2", "https://dx.doi.org/10.1017/S0022109024000930?rft_dat=source%3Ddrss")
    request = _build_fetch_request(journal, entry)
    assert request.url == entry.link
    assert request.headers["Referer"] == "https://www.cambridge.org/"
