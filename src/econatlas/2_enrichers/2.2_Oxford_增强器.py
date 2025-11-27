"""
Oxford 增强器：利用浏览器抓取补充作者信息。
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

from pathlib import Path
from bs4 import BeautifulSoup

from econatlas.models import ArticleRecord, NormalizedFeedEntry
from econatlas.samples import (
    BrowserCredentials,
    PlaywrightFetcher,
    browser_credentials_for_source,
    browser_headless_for_source,
    browser_launch_overrides,
    browser_local_storage_for_source,
    browser_user_agent_for_source,
    browser_wait_selector_for_source,
    build_browser_headers,
    cookies_for_source,
    local_storage_script,
)

LOGGER = logging.getLogger(__name__)
OXFORD_SOURCE_TYPE = "oxford"


class PersistentOxfordSession:
    """维持单个 Playwright 会话，减少 Cloudflare 触发。"""

    def __init__(self) -> None:
        self._playwright = None
        self._browser = None
        self._context = None
        self._throttle_seconds = _throttle_seconds_from_env()

    def ensure_session(
        self,
        *,
        headers: dict[str, str],
        cookies: dict[str, str] | None,
        credentials: BrowserCredentials | None,
        user_agent: str,
        wait_selector: str | None,
        init_scripts: list[str] | None,
        user_data_dir: str | None,
        headless: bool,
        browser_channel: str | None,
        executable_path: str | None,
    ) -> None:
        if self._context:
            return
        if user_data_dir:
            for lock_name in ("SingletonLock", "SingletonCookie", "SingletonSocket"):
                lock_path = Path(user_data_dir) / lock_name
                try:
                    lock_path.unlink()
                except FileNotFoundError:
                    pass
                except OSError:
                    LOGGER.debug("无法移除旧锁 %s", lock_path)

        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "Playwright 未安装。运行 `uv add playwright` 和 `uv run playwright install chromium`。"
            ) from exc

        self._playwright = sync_playwright().start()
        launch_kwargs: dict[str, Any] = {"headless": headless}
        if executable_path:
            launch_kwargs["executable_path"] = executable_path
        elif browser_channel:
            launch_kwargs["channel"] = browser_channel

        if user_data_dir:
            context = self._playwright.chromium.launch_persistent_context(
                user_data_dir,
                **launch_kwargs,
                user_agent=user_agent,
                http_credentials=credentials.as_dict() if credentials else None,
            )
        else:
            browser = self._playwright.chromium.launch(**launch_kwargs)
            context_kwargs: dict[str, Any] = {"user_agent": user_agent}
            if credentials:
                context_kwargs["http_credentials"] = credentials.as_dict()
            context = browser.new_context(**context_kwargs)
            self._browser = browser

        if headers:
            context.set_extra_http_headers(headers)
        if cookies:
            context.add_cookies(
                [
                    {
                        "name": name,
                        "value": value,
                        "domain": "academic.oup.com",
                        "path": "/",
                    }
                    for name, value in cookies.items()
                ]
            )
        if init_scripts:
            for script in init_scripts:
                context.add_init_script(script)

        self._context = context

    def fetch(self, url: str, wait_selector: str | None) -> str:
        if not self._context:
            raise RuntimeError("会话未初始化")
        page = self._context.new_page()
        if self._throttle_seconds > 0:
            time.sleep(self._throttle_seconds)
        page.goto(url, wait_until="domcontentloaded", timeout=45_000)
        if wait_selector:
            try:
                page.wait_for_selector(wait_selector, timeout=45_000)
            except Exception:  # noqa: BLE001
                LOGGER.debug("等待选择器 %s 超时: %s", wait_selector, url)
        html_text = page.content()
        page.close()
        return html_text

    def close(self) -> None:
        try:
            if self._context:
                self._context.close()
            if self._browser:
                self._browser.close()
            if self._playwright:
                self._playwright.stop()
        except Exception:
            LOGGER.debug("关闭 Oxford 会话失败", exc_info=True)
        finally:
            self._context = None
            self._browser = None
            self._playwright = None


class OxfordArticleFetcher:
    def __init__(self, fetcher: PlaywrightFetcher | None = None) -> None:
        self._fetcher = fetcher or PlaywrightFetcher()
        self._session = PersistentOxfordSession()

    def fetch_html(self, url: str) -> str:
        headers = build_browser_headers({"Referer": "https://academic.oup.com/"}, OXFORD_SOURCE_TYPE)
        cookies = cookies_for_source(OXFORD_SOURCE_TYPE)
        credentials = browser_credentials_for_source(OXFORD_SOURCE_TYPE)
        user_agent = browser_user_agent_for_source(OXFORD_SOURCE_TYPE, headers)
        wait_selector = browser_wait_selector_for_source(OXFORD_SOURCE_TYPE)
        init_scripts = []
        local_storage_entries = browser_local_storage_for_source(OXFORD_SOURCE_TYPE)
        if local_storage_entries:
            init_scripts.append(local_storage_script(local_storage_entries))
        user_data_dir = os.getenv("OXFORD_USER_DATA_DIR")
        headless = browser_headless_for_source(OXFORD_SOURCE_TYPE)
        browser_channel, executable_path = browser_launch_overrides(OXFORD_SOURCE_TYPE)
        self._session.ensure_session(
            headers=headers,
            cookies=cookies,
            credentials=credentials,
            user_agent=user_agent,
            wait_selector=wait_selector,
            init_scripts=init_scripts or None,
            user_data_dir=user_data_dir,
            headless=headless,
            browser_channel=browser_channel,
            executable_path=executable_path,
        )
        html_text = self._session.fetch(url, wait_selector=wait_selector)
        return html_text


class OxfordEnricher:
    def __init__(self, fetcher: OxfordArticleFetcher | None = None) -> None:
        self._fetcher = fetcher or OxfordArticleFetcher()
        throttle_env = os.getenv("OXFORD_THROTTLE_SECONDS")
        try:
            self._throttle_seconds = float(throttle_env) if throttle_env else 3.0
        except ValueError:
            self._throttle_seconds = 3.0
        self._closed = False

    def enrich(self, record: ArticleRecord, entry: NormalizedFeedEntry) -> ArticleRecord:
        if record.authors:
            return record
        if not entry.link:
            return record
        if self._throttle_seconds > 0:
            time.sleep(self._throttle_seconds)
        try:
            html = self._fetcher.fetch_html(entry.link)
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Oxford 补全失败 %s: %s", entry.link, exc)
            return record
        authors = _extract_authors(html)
        if not authors:
            return record
        return record.model_copy(update={"authors": authors})

    def close(self) -> None:
        if not self._closed:
            try:
                self._fetcher._session.close()  # type: ignore[attr-defined]
            except Exception:
                LOGGER.debug("关闭 Oxford 会话失败", exc_info=True)
            self._closed = True


def _throttle_seconds_from_env() -> float:
    raw = os.getenv("OXFORD_THROTTLE_SECONDS")
    if not raw:
        return 0.0
    try:
        value = float(raw)
        return value if value > 0 else 0.0
    except ValueError:
        LOGGER.warning("Invalid OXFORD_THROTTLE_SECONDS value: %s", raw)
        return 0.0


def _extract_authors(html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    authors = _authors_from_json_ld(soup)
    if authors:
        return authors
    meta_authors: list[str] = []
    for meta in soup.find_all("meta", attrs={"name": "citation_author"}):
        raw = meta.get("content")
        if isinstance(raw, str):
            trimmed = raw.strip()
            if trimmed:
                meta_authors.append(trimmed)
    return meta_authors


def _authors_from_json_ld(soup: BeautifulSoup) -> list[str]:
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(script.string or "")
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            authors = _coerce_ld_authors(data.get("author"))
            if authors:
                return authors
        elif isinstance(data, list):
            for item in data:
                if not isinstance(item, dict):
                    continue
                authors = _coerce_ld_authors(item.get("author"))
                if authors:
                    return authors
    return []


def _coerce_ld_authors(payload: Any) -> list[str]:
    if not payload:
        return []
    if isinstance(payload, dict):
        name = payload.get("name")
        if isinstance(name, str):
            trimmed = name.strip()
            if trimmed:
                return [trimmed]
        return []
    if isinstance(payload, list):
        result: list[str] = []
        for item in payload:
            result.extend(_coerce_ld_authors(item))
        return result
    if isinstance(payload, str):
        trimmed = payload.strip()
        if trimmed:
            return [trimmed]
    return []
