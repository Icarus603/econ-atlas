"""
CNKI 增强器：在 RSS 基础上用持久化浏览器抓详情页，补充完整摘要。
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

from econatlas.models import ArticleRecord, NormalizedFeedEntry
from econatlas.translation import detect_language
from econatlas._loader import load_local_module

_samples_env = load_local_module(__file__, "../5_samples/5.3_浏览器环境.py", "econatlas._samples_env")
build_browser_headers = _samples_env.build_browser_headers  # type: ignore[attr-defined]
cleanup_user_data_dir = _samples_env.cleanup_user_data_dir  # type: ignore[attr-defined]
browser_credentials_for_source = _samples_env.browser_credentials_for_source  # type: ignore[attr-defined]
browser_user_agent_for_source = _samples_env.browser_user_agent_for_source  # type: ignore[attr-defined]
browser_user_data_dir_for_source = _samples_env.browser_user_data_dir_for_source  # type: ignore[attr-defined]
browser_headless_for_source = _samples_env.browser_headless_for_source  # type: ignore[attr-defined]
browser_launch_overrides = _samples_env.browser_launch_overrides  # type: ignore[attr-defined]
cookies_for_source = _samples_env.cookies_for_source  # type: ignore[attr-defined]

LOGGER = logging.getLogger(__name__)
CNKI_SOURCE_TYPE = "cnki"


@dataclass(frozen=True)
class CnkiConfig:
    max_retries: int = 5
    backoff_seconds: float = 1.0
    throttle_seconds: float = 3.0


class CNKIEnricher:
    """为 CNKI 文章补充摘要。"""

    def __init__(self, config: CnkiConfig | None = None) -> None:
        self._config = config or CnkiConfig(throttle_seconds=_throttle_seconds_from_env())
        self._session = _PersistentBrowserSession(CNKI_SOURCE_TYPE, throttle_seconds=self._config.throttle_seconds)

    def close(self) -> None:
        try:
            self._session.close()
        except Exception:
            LOGGER.debug("关闭 CNKI 会话失败", exc_info=True)

    def enrich(self, record: ArticleRecord, entry: NormalizedFeedEntry) -> ArticleRecord:
        if not entry.link:
            return record
        last_exc: Exception | None = None
        for attempt in range(1, self._config.max_retries + 1):
            try:
                html_text = self._session.fetch(entry.link)
                abstract = _extract_abstract(html_text)
                if abstract and (not record.abstract_original or len(abstract) > len(record.abstract_original or "")):
                    return record.model_copy(
                        update={
                            "abstract_original": abstract,
                            "abstract_language": detect_language(abstract) or record.abstract_language,
                        }
                    )
                return record
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                if attempt == self._config.max_retries:
                    break
                delay = min(self._config.backoff_seconds * attempt, 10.0)
                time.sleep(delay)
        if last_exc:
            LOGGER.warning("CNKI 抽取摘要失败 %s: %s", entry.link, last_exc)
        return record


class _PersistentBrowserSession:
    """持久化浏览器会话，避免频繁重启。"""

    def __init__(self, source_type: str, throttle_seconds: float) -> None:
        self._source_type = source_type
        self._throttle_seconds = throttle_seconds
        self._cookies = cookies_for_source(source_type)
        self._playwright = None
        self._browser = None
        self._context = None

    def _ensure_session(self) -> None:
        if self._context:
            return
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "Playwright 未安装。运行 `uv add playwright` 和 `uv run playwright install chromium`。"
            ) from exc

        user_agent = browser_user_agent_for_source(self._source_type, {})
        headers = build_browser_headers(
            {
                "Referer": "https://kns.cnki.net/",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.5",
            },
            self._source_type,
        )
        credentials = browser_credentials_for_source(self._source_type)
        user_data_dir = browser_user_data_dir_for_source(self._source_type) or os.getenv("BROWSER_USER_DATA_DIR")
        headless = browser_headless_for_source(self._source_type)
        browser_channel, executable_path = browser_launch_overrides(self._source_type)

        if user_data_dir:
            cleanup_user_data_dir(user_data_dir)

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
            self._browser = browser
            context_kwargs: dict[str, Any] = {"user_agent": user_agent}
            if credentials:
                context_kwargs["http_credentials"] = credentials.as_dict()
            context = browser.new_context(**context_kwargs)

        if headers:
            context.set_extra_http_headers(headers)
        if self._cookies:
            context.add_cookies(
                [
                    {"name": name, "value": value, "domain": ".cnki.net", "path": "/"}
                    for name, value in self._cookies.items()
                ]
            )
        # 关闭默认空白页，避免 GUI 下残留 about:blank
        for page in list(context.pages):
            try:
                page.close()
            except Exception:
                LOGGER.debug("关闭默认页面失败", exc_info=True)
        self._context = context

    def fetch(self, url: str) -> str:
        self._ensure_session()
        assert self._context is not None
        if self._throttle_seconds > 0:
            time.sleep(self._throttle_seconds)
        page = self._context.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=45_000)
        try:
            page.wait_for_selector("#ChDivSummary", timeout=45_000)
        except Exception:
            LOGGER.debug("等待摘要节点超时: %s", url)
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
            LOGGER.debug("关闭 CNKI 会话失败", exc_info=True)
        finally:
            self._context = None
            self._browser = None
            self._playwright = None


def _extract_abstract(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    node = soup.find(id="ChDivSummary")
    if node:
        text = node.get_text(" ", strip=True)
        if text:
            return text
    meta = soup.find("meta", attrs={"name": "description"})
    if meta:
        content = meta.get("content")
        if isinstance(content, str) and content.strip():
            return content.strip()
    for div in soup.find_all(["div", "section"]):
        ident_parts = []
        ident_parts.append(str(div.get("id", "")))
        cls = div.get("class")
        if isinstance(cls, list):
            ident_parts.extend(cls)
        elif isinstance(cls, str):
            ident_parts.append(cls)
        ident = " ".join(ident_parts).lower()
        if "摘要" in ident or "abstract" in ident:
            text = div.get_text(" ", strip=True)
            if text:
                return text
    return None


def _throttle_seconds_from_env() -> float:
    raw = os.getenv("CNKI_THROTTLE_SECONDS")
    if not raw:
        return 3.0
    try:
        value = float(raw)
        return value if value > 0 else 0.0
    except ValueError:
        LOGGER.warning("Invalid CNKI_THROTTLE_SECONDS value: %s", raw)
        return 3.0
