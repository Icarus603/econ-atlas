"""
Chicago 爬虫：RSS 拉取后用浏览器抓取页面，补全作者与摘要。
"""

from __future__ import annotations

import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Iterable

from bs4 import BeautifulSoup

from econatlas._loader import load_local_module
from econatlas.models import ArticleRecord, JournalSource, NormalizedFeedEntry, TranslationRecord

_feed_mod = load_local_module(__file__, "../0_feeds/0.1_RSS_抓取.py", "econatlas._feed_rss")
FeedClient = _feed_mod.FeedClient  # type: ignore[attr-defined]

_trans_mod = load_local_module(__file__, "../3_translation/3.1_翻译基础.py", "econatlas._trans_base")
detect_language = _trans_mod.detect_language  # type: ignore[attr-defined]
skipped_translation = _trans_mod.skipped_translation  # type: ignore[attr-defined]

_samples_env = load_local_module(__file__, "../5_samples/5.3_浏览器环境.py", "econatlas._samples_env")
build_browser_headers = _samples_env.build_browser_headers  # type: ignore[attr-defined]
browser_credentials_for_source = _samples_env.browser_credentials_for_source  # type: ignore[attr-defined]
browser_user_agent_for_source = _samples_env.browser_user_agent_for_source  # type: ignore[attr-defined]
browser_wait_selector_for_source = _samples_env.browser_wait_selector_for_source  # type: ignore[attr-defined]
browser_init_scripts_for_source = _samples_env.browser_init_scripts_for_source  # type: ignore[attr-defined]
browser_local_storage_for_source = _samples_env.browser_local_storage_for_source  # type: ignore[attr-defined]
browser_user_data_dir_for_source = _samples_env.browser_user_data_dir_for_source  # type: ignore[attr-defined]
browser_headless_for_source = _samples_env.browser_headless_for_source  # type: ignore[attr-defined]
browser_launch_overrides = _samples_env.browser_launch_overrides  # type: ignore[attr-defined]
cookies_for_source = _samples_env.cookies_for_source  # type: ignore[attr-defined]
local_storage_script = _samples_env.local_storage_script  # type: ignore[attr-defined]

_browser_mod = load_local_module(__file__, "../5_samples/5.2_浏览器抓取.py", "econatlas._samples_fetcher")
PlaywrightFetcher = _browser_mod.PlaywrightFetcher  # type: ignore[attr-defined]

LOGGER = logging.getLogger(__name__)
SOURCE_TYPE = "chicago"


class Chicago爬虫:
    """Chicago 来源：RSS + 浏览器补全摘要/作者。"""

    def __init__(self, feed_client: FeedClient) -> None:
        self._feed_client = feed_client
        self._session = _PersistentBrowserSession(SOURCE_TYPE)
        self._throttle_seconds = _throttle_seconds_from_env(SOURCE_TYPE)

    def crawl(self, journal: JournalSource) -> list[ArticleRecord]:
        entries = self._feed_client.fetch(journal.rss_url)
        records: list[ArticleRecord] = []
        for entry in entries:
            record = _构建基础记录(entry)
            if self._throttle_seconds > 0:
                time.sleep(self._throttle_seconds)
            enriched = self._补全页面信息(record)
            records.append(enriched)
        return records

    def _补全页面信息(self, record: ArticleRecord) -> ArticleRecord:
        if not record.link:
            return record
        try:
            html = self._session.fetch_html(
                record.link,
                referer="https://www.journals.uchicago.edu/",
            )
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Chicago 页面抓取失败 %s: %s", record.link, exc)
            return record
        authors = _提取作者(html)
        abstract = _提取摘要(html)
        update: dict[str, object] = {}
        if authors and not record.authors:
            update["authors"] = authors
        if abstract:
            update["abstract_original"] = abstract
            update["abstract_language"] = detect_language(abstract)
            update["translation"] = TranslationRecord(
                status="skipped",
                translator=None,
                translated_at=datetime.now(timezone.utc),
                error=None,
            )
        if not update:
            return record
        return record.model_copy(update=update)

    def close(self) -> None:
        self._session.close()


def _构建基础记录(entry: NormalizedFeedEntry) -> ArticleRecord:
    """将标准化条目转为 ArticleRecord，占位翻译（不立即翻译）。"""
    summary = entry.summary or ""
    language = detect_language(summary)
    translation_result = skipped_translation(summary)
    return ArticleRecord(
        id=entry.entry_id,
        title=entry.title,
        link=entry.link,
        authors=list(entry.authors),
        published_at=entry.published_at,
        abstract_original=summary or None,
        abstract_language=language,
        abstract_zh=None,
        translation=TranslationRecord(
            status=translation_result.status,
            translator=translation_result.translator,
            translated_at=translation_result.translated_at,
            error=translation_result.error,
        ),
        fetched_at=datetime.now(timezone.utc),
    )


def _抓取_html(
    fetcher: PlaywrightFetcher,
    url: str,
    source_type: str,
    *,
    referer: str,
) -> str:
    headers = build_browser_headers({"Referer": referer}, source_type)
    cookies = cookies_for_source(source_type)
    credentials = browser_credentials_for_source(source_type)
    user_agent = browser_user_agent_for_source(source_type, headers)
    wait_selector = browser_wait_selector_for_source(source_type)
    init_scripts: list[str] = browser_init_scripts_for_source(source_type) or []
    local_storage_entries: Iterable[dict[str, str]] | None = browser_local_storage_for_source(source_type)
    if local_storage_entries:
        init_scripts.append(local_storage_script(local_storage_entries))
    user_data_dir = browser_user_data_dir_for_source(source_type)
    headless = browser_headless_for_source(source_type)
    browser_channel, executable_path = browser_launch_overrides(source_type)
    html_bytes = fetcher.fetch(
        url=url,
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
    return html_bytes.decode("utf-8", errors="ignore")


def _提取作者(html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    names: list[str] = []
    for meta in soup.find_all("meta", attrs={"name": "citation_author"}):
        raw = meta.get("content")
        if isinstance(raw, str):
            trimmed = raw.strip()
            if trimmed:
                names.append(trimmed)
    return names


def _提取摘要(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    for meta_name in ("citation_abstract", "dc.Description", "description"):
        meta = soup.find("meta", attrs={"name": meta_name})
        if meta:
            content = meta.get("content")
            if isinstance(content, str) and content.strip():
                return content.strip()
    og_desc = soup.find("meta", attrs={"property": "og:description"})
    if og_desc:
        content = og_desc.get("content")
        if isinstance(content, str) and content.strip():
            return content.strip()
    return None


class _PersistentBrowserSession:
    """保持单个 Playwright 会话，避免每个 URL 重启浏览器。"""

    def __init__(self, source_type: str) -> None:
        self._source_type = source_type
        self._playwright = None
        self._browser = None
        self._context = None
        self._executor = ThreadPoolExecutor(max_workers=1)

    def _ensure_session(
        self,
        *,
        headers: dict[str, str],
        cookies: dict[str, str] | None,
        credentials: object | None,
        user_agent: str,
        init_scripts: list[str] | None,
        user_data_dir: str | None,
        headless: bool,
        browser_channel: str | None,
        executable_path: str | None,
    ) -> None:
        if self._context:
            return
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "Playwright 未安装。运行 `uv add playwright` 和 `uv run playwright install chromium`。"
            ) from exc
        self._playwright = sync_playwright().start()
        launch_kwargs: dict[str, object] = {"headless": headless}
        if executable_path:
            launch_kwargs["executable_path"] = executable_path
        elif browser_channel:
            launch_kwargs["channel"] = browser_channel

        if user_data_dir:
            context = self._playwright.chromium.launch_persistent_context(
                user_data_dir,
                **launch_kwargs,
                user_agent=user_agent,
                http_credentials=credentials,
            )
        else:
            browser = self._playwright.chromium.launch(**launch_kwargs)
            self._browser = browser
            context_kwargs: dict[str, object] = {"user_agent": user_agent}
            if credentials:
                context_kwargs["http_credentials"] = credentials
            context = browser.new_context(**context_kwargs)

        # 关闭默认空白页，避免 GUI 下出现 about:blank 悬挂页。
        for page in list(context.pages):
            try:
                page.close()
            except Exception:
                LOGGER.debug("关闭默认页面失败", exc_info=True)

        if headers:
            context.set_extra_http_headers(headers)
        if cookies:
            domain = ".journals.uchicago.edu"
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

        self._context = context

    def fetch_html(self, url: str, *, referer: str) -> str:
        headers = build_browser_headers({"Referer": referer}, self._source_type)
        cookies = cookies_for_source(self._source_type)
        credentials = browser_credentials_for_source(self._source_type)
        user_agent = browser_user_agent_for_source(self._source_type, headers)
        wait_selector = browser_wait_selector_for_source(self._source_type)
        init_scripts: list[str] = browser_init_scripts_for_source(self._source_type) or []
        local_storage_entries: Iterable[dict[str, str]] | None = browser_local_storage_for_source(self._source_type)
        if local_storage_entries:
            init_scripts.append(local_storage_script(local_storage_entries))
        user_data_dir = browser_user_data_dir_for_source(self._source_type)
        headless = browser_headless_for_source(self._source_type)
        browser_channel, executable_path = browser_launch_overrides(self._source_type)

        def _run() -> str:
            self._ensure_session(
                headers=headers,
                cookies=cookies,
                credentials=credentials.as_dict() if credentials else None,  # type: ignore[arg-type]
                user_agent=user_agent,
                init_scripts=init_scripts or None,
                user_data_dir=user_data_dir,
                headless=headless,
                browser_channel=browser_channel,
                executable_path=executable_path,
            )
            assert self._context is not None
            page = self._context.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=45_000)
            if wait_selector:
                try:
                    page.wait_for_selector(wait_selector, timeout=45_000)
                except Exception:
                    LOGGER.debug("等待选择器 %s 超时: %s", wait_selector, url)
            html_text = page.content()
            page.close()
            return html_text

        return self._executor.submit(_run).result()

    def close(self) -> None:
        def _close() -> None:
            try:
                if self._context:
                    self._context.close()
                if self._browser:
                    self._browser.close()
                if self._playwright:
                    self._playwright.stop()
            except Exception:
                LOGGER.debug("关闭 Chicago 会话失败", exc_info=True)
            finally:
                self._context = None
                self._browser = None
                self._playwright = None

        try:
            self._executor.submit(_close).result(timeout=10)
        except Exception:
            LOGGER.debug("关闭 Chicago 会话失败", exc_info=True)
        self._executor.shutdown(wait=True, cancel_futures=True)


def _throttle_seconds_from_env(source_type: str) -> float:
    env_key = f"{source_type.upper()}_THROTTLE_SECONDS"
    raw = os.getenv(env_key)
    if not raw:
        return 3.0
    try:
        value = float(raw)
        return value if value > 0 else 0.0
    except ValueError:
        LOGGER.warning("Invalid %s value: %s", env_key, raw)
        return 3.0
