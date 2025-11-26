"""
样本采集：从 RSS 抽取条目并保存 HTML，用于后续解析调试。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from econatlas._loader import load_local_module
from pathlib import Path
from typing import Iterable, Protocol

import httpx
from slugify import slugify

from econatlas.models import JournalSource, NormalizedFeedEntry

_fetcher = load_local_module(__file__, "5.2_浏览器抓取.py", "econatlas._samples_fetcher")
_env = load_local_module(__file__, "5.3_浏览器环境.py", "econatlas._samples_env")

BrowserCredentials = _fetcher.BrowserCredentials  # type: ignore[attr-defined]
PlaywrightFetcher = _fetcher.PlaywrightFetcher  # type: ignore[attr-defined]

BASE_HEADERS = _env.BASE_HEADERS  # type: ignore[attr-defined]
BrowserLaunchConfigurationError = _env.BrowserLaunchConfigurationError  # type: ignore[attr-defined]
browser_credentials_for_source = _env.browser_credentials_for_source  # type: ignore[attr-defined]
browser_extract_script_for_source = _env.browser_extract_script_for_source  # type: ignore[attr-defined]
browser_headless_for_source = _env.browser_headless_for_source  # type: ignore[attr-defined]
browser_init_scripts_for_source = _env.browser_init_scripts_for_source  # type: ignore[attr-defined]
browser_launch_overrides = _env.browser_launch_overrides  # type: ignore[attr-defined]
browser_local_storage_for_source = _env.browser_local_storage_for_source  # type: ignore[attr-defined]
browser_user_agent_for_source = _env.browser_user_agent_for_source  # type: ignore[attr-defined]
browser_user_data_dir_for_source = _env.browser_user_data_dir_for_source  # type: ignore[attr-defined]
browser_wait_selector_for_source = _env.browser_wait_selector_for_source  # type: ignore[attr-defined]
build_browser_headers = _env.build_browser_headers  # type: ignore[attr-defined]
cookies_for_source = _env.cookies_for_source  # type: ignore[attr-defined]
local_storage_script = _env.local_storage_script  # type: ignore[attr-defined]
rewrite_sciencedirect_url = _env.rewrite_sciencedirect_url  # type: ignore[attr-defined]
require_sciencedirect_profile = _env.require_sciencedirect_profile  # type: ignore[attr-defined]


LOGGER = logging.getLogger(__name__)
DEFAULT_FETCH_TIMEOUT = 30.0
DEFAULT_BROWSER_TIMEOUT = 45.0
PROTECTED_SOURCE_TYPES = frozenset({"wiley", "oxford", "sciencedirect", "chicago", "informs"})


class FeedFetcher(Protocol):
    def fetch(self, rss_url: str) -> list[NormalizedFeedEntry]:  # pragma: no cover
        ...


class HtmlFetcher(Protocol):
    def __call__(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        cookies: dict[str, str] | None = None,
    ) -> bytes:  # pragma: no cover
        ...


class BrowserHtmlFetcher(Protocol):
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
        headless: bool = True,
        trace_path: Path | None = None,
        debug_dir: Path | None = None,
        debug_label: str | None = None,
        browser_channel: str | None = None,
        executable_path: str | None = None,
    ) -> bytes:  # pragma: no cover
        ...


@dataclass
class FetchRequest:
    url: str
    headers: dict[str, str]
    cookies: dict[str, str] | None


@dataclass
class JournalSampleReport:
    journal: JournalSource
    saved_files: list[Path]
    errors: list[str]
    browser_attempts: int = 0
    browser_successes: int = 0
    browser_failures: int = 0


@dataclass
class SampleCollectorReport:
    results: list[JournalSampleReport]

    @property
    def total_saved(self) -> int:
        return sum(len(result.saved_files) for result in self.results)

    @property
    def failures(self) -> list[JournalSampleReport]:
        return [result for result in self.results if result.errors]

    @property
    def total_browser_attempts(self) -> int:
        return sum(result.browser_attempts for result in self.results)

    @property
    def total_browser_successes(self) -> int:
        return sum(result.browser_successes for result in self.results)

    @property
    def total_browser_failures(self) -> int:
        return sum(result.browser_failures for result in self.results)


class SampleCollector:
    """下载文章 HTML 样本便于排查来源差异。"""

    def __init__(
        self,
        *,
        feed_client: FeedFetcher,
        fetch_html: HtmlFetcher | None = None,
        browser_fetcher: BrowserHtmlFetcher | None = None,
        sciencedirect_debug: bool = False,
    ):
        self._feed_client = feed_client
        self._fetch_html = fetch_html or _default_fetch_html
        self._browser_fetcher = browser_fetcher
        self._protected_sources = PROTECTED_SOURCE_TYPES.copy()
        self._scd_debug = sciencedirect_debug

    def collect(
        self,
        journals: Iterable[JournalSource],
        *,
        limit_per_journal: int,
        output_dir: Path,
    ) -> SampleCollectorReport:
        results: list[JournalSampleReport] = []
        output_dir.mkdir(parents=True, exist_ok=True)
        scd_debug_dir = (output_dir / "_debug_sciencedirect") if self._scd_debug else None
        for journal in journals:
            report = self._collect_for_journal(
                journal,
                limit_per_journal,
                output_dir,
                debug_dir=scd_debug_dir,
            )
            results.append(report)
        return SampleCollectorReport(results=results)

    def _collect_for_journal(
        self,
        journal: JournalSource,
        limit_per_journal: int,
        output_dir: Path,
        debug_dir: Path | None,
    ) -> JournalSampleReport:
        try:
            entries = self._feed_client.fetch(journal.rss_url)
        except Exception as exc:  # noqa: BLE001
            LOGGER.error("RSS 获取失败 %s: %s", journal.name, exc)
            return JournalSampleReport(journal=journal, saved_files=[], errors=[f"rss: {exc}"])

        target_dir = output_dir / journal.source_type / journal.slug
        target_dir.mkdir(parents=True, exist_ok=True)
        report = JournalSampleReport(journal=journal, saved_files=[], errors=[])
        seen_ids: set[str] = set()

        for entry in entries:
            if limit_per_journal and len(report.saved_files) >= limit_per_journal:
                break
            entry_id = entry.entry_id or entry.link or ""
            if not entry_id:
                report.errors.append("missing entry id")
                continue
            if entry_id in seen_ids:
                continue
            seen_ids.add(entry_id)
            if not entry.link:
                report.errors.append(f"{entry_id}: missing link")
                continue
            request = _build_fetch_request(journal, entry)
            filename = _build_filename(entry)
            debug_label = None
            per_entry_debug_dir = None
            if debug_dir and journal.source_type == "sciencedirect":
                per_entry_debug_dir = debug_dir
                debug_label = filename.rsplit(".", 1)[0]
            try:
                use_browser = journal.source_type in self._protected_sources
                html_bytes = self._fetch_with_strategy(
                    request=request,
                    source_type=journal.source_type,
                    use_browser=use_browser,
                    report=report,
                    debug_dir=per_entry_debug_dir,
                    debug_label=debug_label,
                )
            except Exception as exc:  # noqa: BLE001
                if isinstance(exc, BrowserLaunchConfigurationError):
                    raise
                LOGGER.warning("抓取 HTML 失败 %s (%s): %s", journal.name, entry.link, exc)
                report.errors.append(f"{entry_id}: {exc}")
                continue
            if journal.source_type == "sciencedirect":
                validation_error = _validate_sciencedirect_capture(
                    html_bytes,
                    debug_dir=per_entry_debug_dir,
                    debug_label=debug_label,
                )
                if validation_error:
                    report.errors.append(f"{entry_id}: {validation_error}")
                    continue
            file_path = target_dir / filename
            file_path.write_bytes(html_bytes)
            report.saved_files.append(file_path)
        return report

    def _fetch_with_strategy(
        self,
        *,
        request: FetchRequest,
        source_type: str,
        use_browser: bool,
        report: JournalSampleReport,
        debug_dir: Path | None,
        debug_label: str | None,
    ) -> bytes:
        if use_browser:
            fetcher = self._ensure_browser_fetcher()
            report.browser_attempts += 1
            headers = build_browser_headers(request.headers, source_type)
            credentials = browser_credentials_for_source(source_type)
            user_agent = browser_user_agent_for_source(source_type, headers)
            wait_selector = browser_wait_selector_for_source(source_type)
            extract_script = browser_extract_script_for_source(source_type)
            init_scripts = browser_init_scripts_for_source(source_type)
            local_storage_entries = browser_local_storage_for_source(source_type)
            if local_storage_entries:
                init_scripts.append(local_storage_script(local_storage_entries))
            user_data_dir = browser_user_data_dir_for_source(source_type)
            if source_type == "sciencedirect":
                user_data_dir = require_sciencedirect_profile(user_data_dir)
            headless = browser_headless_for_source(source_type)
            browser_channel, executable_path = browser_launch_overrides(source_type)
            trace_path = None
            if debug_dir and debug_label and source_type == "sciencedirect":
                trace_path = debug_dir / f"{debug_label}.zip"
            try:
                html_bytes = fetcher.fetch(
                    url=request.url,
                    headers=headers,
                    cookies=request.cookies,
                    credentials=credentials,
                    user_agent=user_agent,
                    wait_selector=wait_selector,
                    extract_script=extract_script,
                    init_scripts=init_scripts or None,
                    user_data_dir=user_data_dir,
                    headless=headless,
                    trace_path=trace_path,
                    debug_dir=debug_dir,
                    debug_label=debug_label,
                    browser_channel=browser_channel,
                    executable_path=executable_path,
                )
            except Exception:
                report.browser_failures += 1
                raise
            report.browser_successes += 1
            return html_bytes
        return self._fetch_html(
            request.url,
            headers=request.headers,
            cookies=request.cookies,
        )

    def _ensure_browser_fetcher(self) -> BrowserHtmlFetcher:
        if self._browser_fetcher is None:
            self._browser_fetcher = PlaywrightFetcher(timeout_seconds=DEFAULT_BROWSER_TIMEOUT)
        return self._browser_fetcher


def _default_fetch_html(
    url: str,
    headers: dict[str, str] | None = None,
    cookies: dict[str, str] | None = None,
) -> bytes:
    merged_headers = dict(BASE_HEADERS)
    if headers:
        merged_headers.update(headers)
    cookie_jar = dict(cookies or {})
    if "onlinelibrary.wiley.com" in url and not cookie_jar:
        cookie_jar["wileyplus-feature-flags"] = "gdpr-ok"
    response = httpx.get(
        url,
        timeout=DEFAULT_FETCH_TIMEOUT,
        headers=merged_headers,
        cookies=cookie_jar or None,
        follow_redirects=True,
    )
    response.raise_for_status()
    return response.content


def _build_filename(entry: NormalizedFeedEntry) -> str:
    raw = entry.entry_id or entry.link or entry.title
    candidate = slugify(raw or "entry", lowercase=True, separator="-")
    if not candidate:
        candidate = slugify(entry.title or "entry", lowercase=True, separator="-") or "entry"
    return f"{candidate}.html"


def _build_fetch_request(journal: JournalSource, entry: NormalizedFeedEntry) -> FetchRequest:
    url = entry.link or entry.entry_id
    if not url:
        raise ValueError("entry link missing")
    headers: dict[str, str] = {}
    if journal.source_type == "wiley":
        url = _rewrite_wiley_url(url)
        headers["Referer"] = "https://onlinelibrary.wiley.com/doi/recent"
    elif journal.source_type == "cambridge":
        headers["Referer"] = "https://www.cambridge.org/"
    elif journal.source_type == "oxford":
        headers["Referer"] = "https://academic.oup.com/"
    elif journal.source_type == "chicago":
        headers["Referer"] = "https://www.journals.uchicago.edu/"
    elif journal.source_type == "sciencedirect":
        url = rewrite_sciencedirect_url(url)
        headers["Referer"] = "https://www.sciencedirect.com/"
    elif journal.source_type == "informs":
        headers["Referer"] = "https://pubsonline.informs.org/"
    elif journal.source_type == "nber":
        headers["Referer"] = "https://www.nber.org/"
    cookies = cookies_for_source(journal.source_type)
    return FetchRequest(url=url, headers=headers, cookies=cookies)


def _rewrite_wiley_url(url: str) -> str:
    if "onlinelibrary.wiley.com" not in url:
        return url
    clean = url.split("?", 1)[0]
    marker = "/doi/"
    if marker in clean and "/doi/abs/" not in clean and "/doi/full/" not in clean:
        return clean.replace(marker, "/doi/abs/", 1)
    return clean


def _validate_sciencedirect_capture(
    html_bytes: bytes,
    *,
    debug_dir: Path | None,
    debug_label: str | None,
) -> str | None:
    text = html_bytes.decode("utf-8", errors="ignore")
    if "browser-snapshot-data" in text or "__NEXT_DATA__" in text:
        return None
    message = (
        "ScienceDirect 未找到 window.__NEXT_DATA__；请先预热，再用 --sdir-debug 查看调试文件。"
    )
    artifacts = _scd_debug_artifacts(debug_dir, debug_label)
    if artifacts:
        joined = ", ".join(artifacts)
        message = f"{message} 调试文件: {joined}"
    return message


def _scd_debug_artifacts(debug_dir: Path | None, debug_label: str | None) -> list[str]:
    if not debug_dir or not debug_label:
        return []
    paths = [
        debug_dir / f"{debug_label}.png",
        debug_dir / f"{debug_label}.json",
        debug_dir / f"{debug_label}.html",
        debug_dir / f"{debug_label}.zip",
    ]
    return [str(path) for path in paths if path.exists()]
