from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, TYPE_CHECKING, cast
from urllib.parse import urlparse
import json
import re

if TYPE_CHECKING:  # pragma: no cover
    from playwright.sync_api import HttpCredentials

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
        wait_selector: str | None = None,
        extract_script: str | None = None,
        init_scripts: Iterable[str] | None = None,
        user_data_dir: str | None = None,
        debug_dir: Path | None = None,
        debug_label: str | None = None,
        headless: bool = True,
        trace_path: Path | None = None,
        browser_channel: str | None = None,
        executable_path: str | None = None,
    ) -> bytes:
        lock_files: list[Path] = []
        if user_data_dir:
            base = Path(user_data_dir)
            lock_files = [
                base / "SingletonLock",
                base / "SingletonCookie",
                base / "SingletonSocket",
            ]
            for lock_path in lock_files:
                try:
                    lock_path.unlink()
                except FileNotFoundError:
                    pass
                except OSError:
                    LOGGER.debug("Could not remove pre-existing lock %s", lock_path)
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
                browser = None
                http_credentials: HttpCredentials | None = None
                if credentials:
                    http_credentials = cast(HttpCredentials, credentials.as_dict())
                launch_kwargs: dict[str, Any] = {"headless": headless}
                if executable_path:
                    launch_kwargs["executable_path"] = executable_path
                elif browser_channel:
                    launch_kwargs["channel"] = browser_channel
                if user_data_dir:
                    context = playwright.chromium.launch_persistent_context(
                        user_data_dir,
                        **launch_kwargs,
                        user_agent=user_agent,
                        http_credentials=http_credentials,
                    )
                else:
                    browser = playwright.chromium.launch(**launch_kwargs)
                    context_kwargs: dict[str, Any] = {"user_agent": user_agent}
                    if http_credentials:
                        context_kwargs["http_credentials"] = http_credentials
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
                if init_scripts:
                    for script in init_scripts:
                        context.add_init_script(script)
                if trace_path:
                    context.tracing.start(screenshots=True, snapshots=True, sources=False)
                page = context.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=self._timeout_ms)
                if wait_selector:
                    try:
                        page.wait_for_selector(wait_selector, timeout=self._timeout_ms)
                    except PlaywrightTimeoutError:
                        LOGGER.debug("wait selector %s timed out for %s", wait_selector, url)
                if self._idle_wait_ms:
                    try:
                        page.wait_for_load_state("networkidle", timeout=self._idle_wait_ms)
                    except PlaywrightTimeoutError:
                        LOGGER.debug("networkidle wait timed out for %s; returning DOM after DOMContentLoaded", url)
                if extract_script:
                    script_content = page.evaluate(f"JSON.stringify({extract_script})")
                    if script_content and script_content != "null":
                        encoded = json.dumps(script_content)
                        page.evaluate(
                            f"""
const pre = document.createElement('pre');
pre.id = 'browser-snapshot-data';
pre.setAttribute('data-source', {repr(extract_script)});
pre.textContent = {encoded};
document.body.appendChild(pre);
"""
                        )
                html_text = page.content()
                if debug_dir:
                    debug_dir.mkdir(parents=True, exist_ok=True)
                    safe_label = _safe_label(debug_label or url)
                    screenshot_path = debug_dir / f"{safe_label}.png"
                    meta_path = debug_dir / f"{safe_label}.json"
                    dom_path = debug_dir / f"{safe_label}.html"
                    page.screenshot(path=str(screenshot_path), full_page=True)
                    meta = {"url": page.url, "title": page.title()}
                    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
                    dom_path.write_text(html_text, encoding="utf-8")
                    LOGGER.info("Saved debug snapshot %s", screenshot_path)
                if trace_path:
                    trace_path.parent.mkdir(parents=True, exist_ok=True)
                    context.tracing.stop(path=str(trace_path))
                    LOGGER.info("Saved debug trace %s", trace_path)
                context.close()
                if browser:
                    browser.close()
        except PlaywrightTimeoutError as exc:
            raise TimeoutError(f"Timed out while waiting for {url} to finish loading") from exc
        except Exception:
            raise
        finally:
            for lock_path in lock_files:
                try:
                    lock_path.unlink()
                except FileNotFoundError:
                    pass
                except OSError:
                    LOGGER.debug("Could not remove lock %s", lock_path)
        return html_text.encode("utf-8")


def _cookie_domain(url: str) -> str | None:
    parsed = urlparse(url)
    return parsed.hostname


def _safe_label(label: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "_", label) or "page"
