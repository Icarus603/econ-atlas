from __future__ import annotations

import json
from datetime import datetime

import pytest

from econ_atlas.ingest.feed import FeedClient

RSS_SAMPLE = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Example Feed</title>
    <item>
      <title>One</title>
      <link>https://example.com/one</link>
      <guid>abc-1</guid>
      <description>Summary</description>
      <pubDate>Mon, 10 Nov 2025 10:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""


class DummyResponse:
    def __init__(
        self,
        *,
        text: str,
        headers: dict[str, str] | None = None,
    ):
        self.text = text
        self.headers = headers or {}

    def raise_for_status(self) -> None:
        return None


def test_feed_client_applies_custom_headers_and_cookies(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, dict | None] = {}

    def fake_get(url: str, timeout: float, headers: dict[str, str], cookies: dict[str, str] | None):
        captured["headers"] = headers
        captured["cookies"] = cookies
        return DummyResponse(text=RSS_SAMPLE, headers={"Content-Type": "application/rss+xml"})

    monkeypatch.setattr("econ_atlas.ingest.feed.httpx.get", fake_get)

    client = FeedClient()
    entries = client.fetch("https://example.com/feed")

    assert entries and entries[0].entry_id == "abc-1"
    headers = captured["headers"]
    assert headers
    assert "Mozilla/5.0" in headers["User-Agent"]
    assert captured["cookies"] is None


class StubBrowserFetcher:
    def __init__(self, payload: bytes):
        self.payload = payload
        self.calls: list[dict[str, str] | None] = []

    def fetch(self, *, url: str, headers: dict[str, str], cookies, credentials, user_agent: str) -> bytes:
        self.calls.append({"url": url, "user_agent": user_agent, "cookies": cookies})
        return self.payload


def test_feed_client_parses_json_feed(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "results": {
            "items": [
                {
                    "id": "w12345",
                    "title": "Sample Working Paper",
                    "abstract": "Details",
                    "permalink": "https://www.nber.org/papers/w12345",
                    "authors": [{"name": "Alice"}, "Bob"],
                    "public_date": "2025-11-01T00:00:00Z",
                }
            ]
        }
    }

    def fake_get(url: str, timeout: float, headers: dict[str, str], cookies: dict[str, str] | None):
        return DummyResponse(
            text=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )

    monkeypatch.setattr("econ_atlas.ingest.feed.httpx.get", fake_get)

    client = FeedClient()
    entries = client.fetch("https://www.nber.org/api/v1/working_page_listing/contentType/working_paper/_/_/search")
    assert len(entries) == 1
    entry = entries[0]
    assert entry.entry_id == "w12345"
    assert entry.link == "https://www.nber.org/papers/w12345"
    assert entry.title == "Sample Working Paper"
    assert entry.summary == "Details"
    assert entry.authors == ["Alice", "Bob"]
    assert isinstance(entry.published_at, datetime)


def test_feed_client_uses_browser_for_protected_hosts(monkeypatch: pytest.MonkeyPatch) -> None:
    browser = StubBrowserFetcher(RSS_SAMPLE.encode("utf-8"))

    def fail_http_get(*args, **kwargs):
        raise AssertionError("httpx should not be called for protected hosts")

    monkeypatch.setattr("econ_atlas.ingest.feed.httpx.get", fail_http_get)
    monkeypatch.setenv("CHICAGO_COOKIES", "foo=bar; baz=qux==")

    client = FeedClient(browser_fetcher=browser)
    entries = client.fetch("https://www.journals.uchicago.edu/action/showFeed?type=etoc&feed=rss&jc=jpe")
    assert entries and entries[0].title == "One"
    assert browser.calls
    call = browser.calls[0]
    assert call["cookies"] == {"foo": "bar", "baz": "qux=="}
