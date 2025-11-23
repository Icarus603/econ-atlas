from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import pytest

from econ_atlas.models import JournalSource, NormalizedFeedEntry
from econ_atlas.source_profiling.browser_env import (
    browser_user_agent_for_source,
    browser_wait_selector_for_source,
    build_browser_headers,
    parse_cookie_header,
)
from econ_atlas.source_profiling.sample_collector import (
    BrowserLaunchConfigurationError,
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
        source_type="cambridge",
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
    saved_dir = tmp_path / "cambridge" / "journal"
    assert (saved_dir / "id-1.html").read_bytes() == b"<html>one</html>"
    assert (saved_dir / "id-2.html").read_bytes() == b"<html>two</html>"
    assert not report.failures


def test_sample_collector_records_errors(tmp_path: Path) -> None:
    journal = JournalSource(
        name="Journal",
        rss_url="https://example.com/rss",
        slug="journal",
        source_type="cambridge",
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


def test_build_fetch_request_sciencedirect_rewrites_abs() -> None:
    journal = JournalSource(
        name="Journal",
        rss_url="https://example.com/rss",
        slug="journal",
        source_type="sciencedirect",
    )
    entry = _entry("id-3", "https://www.sciencedirect.com/science/article/abs/pii/S0047272725001975")
    request = _build_fetch_request(journal, entry)
    assert request.url == "https://www.sciencedirect.com/science/article/pii/S0047272725001975"
    assert request.headers["Referer"] == "https://www.sciencedirect.com/"


def test_browser_launch_channel_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("WILEY_BROWSER_CHANNEL", "chrome")
    journal = JournalSource(
        name="Journal",
        rss_url="https://example.com/rss",
        slug="journal",
        source_type="wiley",
    )
    entry = _entry("id-1", "https://example.com/one")
    feed_client = StubFeedClient({"https://example.com/rss": [entry]})
    browser_fetcher = StubBrowserFetcher({"https://example.com/one": b"<html/>"})
    collector = SampleCollector(feed_client=feed_client, browser_fetcher=browser_fetcher)
    collector.collect([journal], output_dir=tmp_path, limit_per_journal=1)
    assert browser_fetcher.last_browser_channel == "chrome"
    assert browser_fetcher.last_executable_path is None


def test_browser_launch_executable_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("WILEY_BROWSER_EXECUTABLE", "~/Applications/Chrome")
    journal = JournalSource(
        name="Journal",
        rss_url="https://example.com/rss",
        slug="journal",
        source_type="wiley",
    )
    entry = _entry("id-1", "https://example.com/one")
    feed_client = StubFeedClient({"https://example.com/rss": [entry]})
    browser_fetcher = StubBrowserFetcher({"https://example.com/one": b"<html/>"})
    collector = SampleCollector(feed_client=feed_client, browser_fetcher=browser_fetcher)
    collector.collect([journal], output_dir=tmp_path, limit_per_journal=1)
    assert browser_fetcher.last_browser_channel is None
    assert browser_fetcher.last_executable_path is not None
    assert browser_fetcher.last_executable_path.endswith("Applications/Chrome")


def test_browser_launch_options_conflict(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("WILEY_BROWSER_CHANNEL", "chrome")
    monkeypatch.setenv("WILEY_BROWSER_EXECUTABLE", "/Applications/Google Chrome.app")
    journal = JournalSource(
        name="Journal",
        rss_url="https://example.com/rss",
        slug="journal",
        source_type="wiley",
    )
    entry = _entry("id-1", "https://example.com/one")
    feed_client = StubFeedClient({"https://example.com/rss": [entry]})
    browser_fetcher = StubBrowserFetcher({"https://example.com/one": b"<html/>"})
    collector = SampleCollector(feed_client=feed_client, browser_fetcher=browser_fetcher)
    with pytest.raises(BrowserLaunchConfigurationError):
        collector.collect([journal], output_dir=tmp_path, limit_per_journal=1)


class StubBrowserFetcher:
    def __init__(self, payloads: dict[str, bytes], should_fail: bool = False):
        self.payloads = payloads
        self.calls = 0
        self.should_fail = should_fail
        self.last_wait_selector: str | None = None
        self.last_extract_script: str | None = None
        self.last_init_scripts: Iterable[str] | None = None
        self.last_user_data_dir: str | None = None
        self.last_browser_channel: str | None = None
        self.last_executable_path: str | None = None

    def fetch(
        self,
        *,
        url: str,
        headers: dict[str, str],
        cookies: dict[str, str] | None,
        credentials: object,
        user_agent: str,
        wait_selector: str | None = None,
        extract_script: str | None = None,
        init_scripts: Iterable[str] | None = None,
        user_data_dir: str | None = None,
        headless: bool = True,
        trace_path: Path | None = None,
        debug_dir: Path | None = None,
        debug_label: str | None = None,
        browser_channel: str | None = None,
        executable_path: str | None = None,
    ) -> bytes:
        self.calls += 1
        self.last_wait_selector = wait_selector
        self.last_extract_script = extract_script
        self.last_init_scripts = init_scripts
        self.last_user_data_dir = user_data_dir
        self.last_headless = headless
        self.last_trace_path = trace_path
        self.last_debug_dir = debug_dir
        self.last_debug_label = debug_label
        self.last_browser_channel = browser_channel
        self.last_executable_path = executable_path
        if self.should_fail:
            raise RuntimeError("browser failed")
        return self.payloads[url]


def test_protected_source_routes_through_browser(tmp_path: Path) -> None:
    journal = JournalSource(
        name="Journal",
        rss_url="https://example.com/rss",
        slug="journal",
        source_type="wiley",
    )
    entries = [_entry("id-1", "https://example.com/one"), _entry("id-2", "https://example.com/two")]
    feed_client = StubFeedClient({"https://example.com/rss": entries})
    payloads = {
        "https://example.com/one": b"<html>browser-one</html>",
        "https://example.com/two": b"<html>browser-two</html>",
    }
    browser_fetcher = StubBrowserFetcher(payloads)

    def fail_if_called(*args: object, **kwargs: object) -> bytes:
        raise AssertionError("HTTP fetch should not be used for protected sources")

    collector = SampleCollector(
        feed_client=feed_client,
        fetch_html=fail_if_called,
        browser_fetcher=browser_fetcher,
    )
    report = collector.collect([journal], limit_per_journal=5, output_dir=tmp_path)

    assert browser_fetcher.calls == 2
    saved_dir = tmp_path / "wiley" / "journal"
    assert (saved_dir / "id-1.html").read_bytes() == b"<html>browser-one</html>"
    assert report.results[0].browser_attempts == 2
    assert report.results[0].browser_successes == 2
    assert report.results[0].browser_failures == 0


def test_browser_failures_are_tracked(tmp_path: Path) -> None:
    journal = JournalSource(
        name="Journal",
        rss_url="https://example.com/rss",
        slug="journal",
        source_type="wiley",
    )
    entries = [_entry("id-1", "https://example.com/one")]
    feed_client = StubFeedClient({"https://example.com/rss": entries})
    browser_fetcher = StubBrowserFetcher({}, should_fail=True)

    collector = SampleCollector(
        feed_client=feed_client,
        browser_fetcher=browser_fetcher,
    )
    report = collector.collect([journal], limit_per_journal=2, output_dir=tmp_path)

    result = report.results[0]
    assert browser_fetcher.calls == 1
    assert result.browser_attempts == 1
    assert result.browser_failures == 1
    assert result.browser_successes == 0
    assert not result.saved_files


def test_parse_cookie_header_strips_quotes() -> None:
    value = "\"foo=bar; baz=qux==; token='abc'\""
    parsed = parse_cookie_header(value)
    assert parsed == {"foo": "bar", "baz": "qux==", "token": "abc"}


def test_browser_headers_override_via_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "WILEY_BROWSER_HEADERS",
        '{"Accept-Language":"zh-HK","sec-ch-ua":"\\"Chromium\\";v=\\"142\\""}',
    )
    headers = build_browser_headers({"User-Agent": "default-agent"}, "wiley")
    assert headers["Accept-Language"] == "zh-HK"
    assert headers["sec-ch-ua"] == '"Chromium";v="142"'


def test_browser_user_agent_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WILEY_BROWSER_USER_AGENT", "custom-ua")
    headers = {"User-Agent": "fallback"}
    assert browser_user_agent_for_source("wiley", headers) == "custom-ua"
    monkeypatch.delenv("WILEY_BROWSER_USER_AGENT", raising=False)
    assert browser_user_agent_for_source("wiley", headers) == "fallback"


def test_sciencedirect_wait_selector_mapping() -> None:
    assert browser_wait_selector_for_source("sciencedirect") == "script#__NEXT_DATA__"
    assert browser_wait_selector_for_source("wiley") is None


def test_sciencedirect_uses_wait_selector_and_rewritten_url(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    journal = JournalSource(
        name="SciDir",
        rss_url="https://example.com/rss",
        slug="sci",
        source_type="sciencedirect",
    )
    entry = _entry("id-10", "https://www.sciencedirect.com/science/article/abs/pii/S0047272725001975")
    feed_client = StubFeedClient({"https://example.com/rss": [entry]})
    rewritten_url = "https://www.sciencedirect.com/science/article/pii/S0047272725001975"
    browser_fetcher = StubBrowserFetcher({rewritten_url: b"<html>scd</html>"})

    collector = SampleCollector(
        feed_client=feed_client,
        browser_fetcher=browser_fetcher,
    )
    profile_dir = tmp_path / "profile"
    profile_dir.mkdir()
    monkeypatch.setenv("SCIENCEDIRECT_USER_DATA_DIR", str(profile_dir))
    monkeypatch.setenv("SCIENCEDIRECT_BROWSER_HEADLESS", "1")
    collector.collect([journal], limit_per_journal=1, output_dir=tmp_path)

    assert browser_fetcher.last_wait_selector == "script#__NEXT_DATA__"
    assert browser_fetcher.last_extract_script == "window.__NEXT_DATA__"
    assert browser_fetcher.last_init_scripts is not None
    assert browser_fetcher.last_headless is True


def test_sciencedirect_requires_profile(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    journal = JournalSource(
        name="SciDir",
        rss_url="https://example.com/rss",
        slug="sci",
        source_type="sciencedirect",
    )
    entry = _entry("id-1", "https://www.sciencedirect.com/science/article/pii/S0047272725001975")
    feed_client = StubFeedClient({"https://example.com/rss": [entry]})
    browser_fetcher = StubBrowserFetcher(
        {"https://www.sciencedirect.com/science/article/pii/S0047272725001975": b"<html>ok</html>"}
    )
    monkeypatch.delenv("SCIENCEDIRECT_USER_DATA_DIR", raising=False)

    collector = SampleCollector(
        feed_client=feed_client,
        browser_fetcher=browser_fetcher,
    )
    report = collector.collect([journal], limit_per_journal=1, output_dir=tmp_path)
    assert "ScienceDirect sampling requires SCIENCEDIRECT_USER_DATA_DIR" in report.results[0].errors[0]


def test_sciencedirect_missing_json_marks_failure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    journal = JournalSource(
        name="SciDir",
        rss_url="https://example.com/rss",
        slug="sci",
        source_type="sciencedirect",
    )
    entry = _entry("id-1", "https://www.sciencedirect.com/science/article/pii/S0047272725001975")
    feed_client = StubFeedClient({"https://example.com/rss": [entry]})
    profile_dir = tmp_path / "profile"
    profile_dir.mkdir()
    monkeypatch.setenv("SCIENCEDIRECT_USER_DATA_DIR", str(profile_dir))
    browser_fetcher = StubBrowserFetcher(
        {"https://www.sciencedirect.com/science/article/pii/S0047272725001975": b"<html>fallback</html>"}
    )

    collector = SampleCollector(
        feed_client=feed_client,
        browser_fetcher=browser_fetcher,
    )
    report = collector.collect([journal], limit_per_journal=1, output_dir=tmp_path)
    result = report.results[0]
    assert result.saved_files == []
    assert any("window.__NEXT_DATA__" in message for message in result.errors)
