from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

LOGGER = logging.getLogger(__name__)


@dataclass
class BrowserCredentials:
    """Simple container for HTTP credentials applied to browser contexts."""

    username: str
    password: str

    def as_dict(self) -> dict[str, str]:
        return {"username": self.username, "password": self.password}


class PlaywrightFetcher:
    """Fetches HTML using Playwright headless Chromium."""

    def __init__(self, *, timeout_seconds: float = 45.0, idle_wait_seconds: float = 5.0):
        self._timeout_ms = int(timeout_seconds * 1000)
        self._idle_wait_ms = int(idle_wait_seconds * 1000)

    def fetch(
        self,
        *,
        url: str,
        headers: dict[str, str],
        cookies: dict[str, str] | None,
        credentials: BrowserCredentials | None,
        user_agent: str,
    ) -> bytes:
        try:
            from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
            from playwright.sync_api import sync_playwright
        except ImportError as exc:  # pragma: no cover - import guard
            raise RuntimeError(
                "Playwright is not installed. Run `uv add playwright` and `uv run playwright install chromium`."
            ) from exc

        extra_headers = dict(headers)
        extra_headers.setdefault("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8")
        extra_headers.setdefault("Accept-Language", "en-US,en;q=0.9")
        extra_headers.pop("User-Agent", None)

        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                context_kwargs: dict[str, Any] = {"user_agent": user_agent}
                if credentials:
                    context_kwargs["http_credentials"] = credentials.as_dict()
                context = browser.new_context(**context_kwargs)
                if extra_headers:
                    context.set_extra_http_headers(extra_headers)
                if cookies:
                    domain = _cookie_domain(url)
                    if domain:
                        context.add_cookies(
                            [
                                {
                                    "name": name,
                                    "value": value,
                                    "domain": domain,
                                    "path": "/",
                                }
                                for name, value in cookies.items()
                            ]
                        )
                page = context.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=self._timeout_ms)
                if self._idle_wait_ms:
                    try:
                        page.wait_for_load_state("networkidle", timeout=self._idle_wait_ms)
                    except PlaywrightTimeoutError:
                        LOGGER.debug("networkidle wait timed out for %s; returning DOM after DOMContentLoaded", url)
                html = page.content()
                context.close()
                browser.close()
        except PlaywrightTimeoutError as exc:
            raise TimeoutError(f"Timed out while waiting for {url} to finish loading") from exc
        except Exception:
            raise
        return html.encode("utf-8")


def _cookie_domain(url: str) -> str | None:
    parsed = urlparse(url)
    return parsed.hostname
