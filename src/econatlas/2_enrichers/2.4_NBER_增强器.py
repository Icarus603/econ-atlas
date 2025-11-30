"""
NBER 增强器：使用 NBER 单篇 API 或页面抓取补全摘要。
"""

from __future__ import annotations

import logging
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

from econatlas.models import ArticleRecord, NormalizedFeedEntry
from econatlas.translation import detect_language
from econatlas._loader import load_local_module

LOGGER = logging.getLogger(__name__)

NBER_ID_REGEX = re.compile(r"/w(\d+)", re.IGNORECASE)


@dataclass(frozen=True)
class NberConfig:
    max_retries: int = 5
    backoff_seconds: float = 1.0
    cookies: str | None = None
    throttle_seconds: float = 3.0


class NBEREnricher:
    """为 NBER 文章补充摘要，优先使用官方 JSON API。"""

    def __init__(self, config: NberConfig | None = None) -> None:
        raw_cookies = os.getenv("NBER_COOKIES")
        throttle = _throttle_seconds_from_env()
        self._config = config or NberConfig(cookies=raw_cookies, throttle_seconds=throttle)
        self._browser = _PersistentBrowserSession(throttle_seconds=self._config.throttle_seconds)

    def close(self) -> None:
        try:
            self._browser.close()
        except Exception:
            LOGGER.debug("关闭 NBER 浏览器会话失败", exc_info=True)

    def enrich(self, record: ArticleRecord, entry: NormalizedFeedEntry) -> ArticleRecord:
        if not entry.link:
            return record
        abstract: str | None = None
        last_exc: Exception | None = None
        for attempt in range(1, self._config.max_retries + 1):
            try:
                LOGGER.info("NBER 抽取摘要 %s (attempt %s/%s)", entry.link, attempt, self._config.max_retries)
                html = self._fetch_html(entry.link)
                abstract = _extract_abstract(html)
                break
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                if attempt == self._config.max_retries:
                    break
                delay = min(self._config.backoff_seconds * attempt, 10.0)
                time.sleep(delay)
        if last_exc and not abstract:
            LOGGER.warning("NBER 抽取摘要失败 %s: %s", entry.link, last_exc)
        if abstract and (not record.abstract_original or len(abstract) > len(record.abstract_original)):
            return record.model_copy(
                update={
                    "abstract_original": abstract,
                    "abstract_language": detect_language(abstract) or record.abstract_language,
                }
            )
        return record

    def _fetch_html(self, url: str) -> str:
        # 直接使用浏览器会话抓取，避免 teaser。
        return self._browser.fetch(url)


def _extract_nber_id(url: str) -> str | None:
    m = NBER_ID_REGEX.search(url)
    if m:
        return m.group(1)
    return None


def _extract_abstract_from_api(payload: dict[str, Any]) -> str | None:
    abstract = payload.get("abstract")
    if isinstance(abstract, str) and abstract.strip():
        return abstract.strip()
    return None


def _extract_abstract(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    candidates = []
    node = soup.find(id="abstract")
    if node:
        candidates.append(node)
    # 常见 class/id 包含 abstract 的容器
    for cls in ["abstract", "field--name-field-working-paper-abstract", "field--name-field-abstract"]:
        candidates.extend(soup.find_all(class_=cls))
    for tag in soup.find_all(["section", "div", "article"]):
        ident_parts = []
        ident_parts.append(str(tag.get("id", "")))
        cls_attr = tag.get("class")
        if isinstance(cls_attr, list):
            ident_parts.extend(cls_attr)
        elif isinstance(cls_attr, str):
            ident_parts.append(cls_attr)
        ident = " ".join(ident_parts).lower()
        if "abstract" in ident:
            candidates.append(tag)
    for cand in candidates:
        text = cand.get_text(" ", strip=True)
        if text:
            return text
    for meta_name in ("description", "og:description"):
        meta = soup.find("meta", attrs={"name": meta_name})
        if meta:
            content = meta.get("content")
            if isinstance(content, str) and content.strip():
                return content.strip()
    return None


# 浏览器持久会话（复用全局设置，与 Wiley/Chicago 模式一致）
_samples_env = load_local_module(__file__, "../5_samples/5.3_浏览器环境.py", "econatlas._samples_env")
build_browser_headers = _samples_env.build_browser_headers  # type: ignore[attr-defined]
browser_credentials_for_source = _samples_env.browser_credentials_for_source  # type: ignore[attr-defined]
browser_user_agent_for_source = _samples_env.browser_user_agent_for_source  # type: ignore[attr-defined]
browser_user_data_dir_for_source = _samples_env.browser_user_data_dir_for_source  # type: ignore[attr-defined]
browser_headless_for_source = _samples_env.browser_headless_for_source  # type: ignore[attr-defined]
browser_launch_overrides = _samples_env.browser_launch_overrides  # type: ignore[attr-defined]
cookies_for_source = _samples_env.cookies_for_source  # type: ignore[attr-defined]
cleanup_user_data_dir = _samples_env.cleanup_user_data_dir  # type: ignore[attr-defined]


class _PersistentBrowserSession:
    def __init__(self, throttle_seconds: float) -> None:
        self._throttle_seconds = throttle_seconds
        self._cookies = cookies_for_source("nber")
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

        user_agent = browser_user_agent_for_source("nber", {})
        headers = build_browser_headers(
            {
                "Referer": "https://www.nber.org/",
                "Accept-Language": "en-US,en;q=0.9,zh;q=0.6",
            },
            "nber",
        )
        credentials = browser_credentials_for_source("nber")
        user_data_dir = browser_user_data_dir_for_source("nber") or os.getenv("BROWSER_USER_DATA_DIR")
        headless = browser_headless_for_source("nber")
        browser_channel, executable_path = browser_launch_overrides("nber")

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
                    {"name": name, "value": value, "domain": ".nber.org", "path": "/"}
                    for name, value in self._cookies.items()
                ]
            )
        # 关闭默认空白页
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
            page.wait_for_selector("#abstract", timeout=30_000)
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
            LOGGER.debug("关闭 NBER 会话失败", exc_info=True)
        finally:
            self._context = None
            self._browser = None
            self._playwright = None


def _throttle_seconds_from_env() -> float:
    raw = os.getenv("NBER_THROTTLE_SECONDS")
    if not raw:
        return 3.0
    try:
        value = float(raw)
        return value if value > 0 else 0.0
    except ValueError:
        LOGGER.warning("Invalid NBER_THROTTLE_SECONDS value: %s", raw)
        return 3.0
