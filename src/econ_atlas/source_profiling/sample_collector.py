from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Protocol

import httpx
from slugify import slugify

from econ_atlas.models import JournalSource, NormalizedFeedEntry
from econ_atlas.source_profiling.browser_fetcher import BrowserCredentials, PlaywrightFetcher

LOGGER = logging.getLogger(__name__)
DEFAULT_FETCH_TIMEOUT = 30.0
DEFAULT_BROWSER_TIMEOUT = 45.0
BASE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


class FeedFetcher(Protocol):
    def fetch(self, rss_url: str) -> list[NormalizedFeedEntry]:  # pragma: no cover - protocol signature
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
    ) -> bytes:  # pragma: no cover - protocol hook
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


class BrowserLaunchConfigurationError(RuntimeError):
    """Raised when browser launch overrides are misconfigured."""

    @property
    def succeeded(self) -> bool:
        return not self.errors


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
    """Downloads article HTML samples for later inspection."""

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
            LOGGER.error("Failed to fetch RSS for %s: %s", journal.name, exc)
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
                LOGGER.warning("Failed to fetch HTML for %s (%s): %s", journal.name, entry.link, exc)
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
            headers = _browser_headers(request.headers, source_type)
            credentials = _browser_credentials_for_source(source_type)
            user_agent = _browser_user_agent_for_source(source_type, headers)
            wait_selector = _browser_wait_selector_for_source(source_type)
            extract_script = _browser_extract_script_for_source(source_type)
            init_scripts = _browser_init_scripts_for_source(source_type)
            local_storage_entries = _browser_local_storage_for_source(source_type)
            if local_storage_entries:
                init_scripts.append(_local_storage_script(local_storage_entries))
            user_data_dir = _browser_user_data_dir_for_source(source_type)
            if source_type == "sciencedirect":
                user_data_dir = _require_sciencedirect_profile(user_data_dir)
            headless = _browser_headless_for_source(source_type)
            browser_channel, executable_path = _browser_launch_overrides(source_type)
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
    # Wiley requires a cookie to signal GDPR consent; emulate default when none provided
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


def _browser_headers(headers: dict[str, str], source_type: str) -> dict[str, str]:
    merged = dict(BASE_HEADERS)
    merged.update(headers)
    extra = _browser_headers_from_env(source_type)
    if extra:
        merged.update(extra)
    return merged


def _browser_headers_from_env(source_type: str) -> dict[str, str] | None:
    env_key = f"{source_type.upper()}_BROWSER_HEADERS"
    raw = os.getenv(env_key)
    if not raw:
        return None
    parsed = _parse_header_mapping(raw)
    return parsed or None


def _browser_user_agent_for_source(source_type: str, headers: dict[str, str]) -> str:
    env_key = f"{source_type.upper()}_BROWSER_USER_AGENT"
    env_value = os.getenv(env_key)
    if env_value:
        return env_value.strip()
    return headers.get("User-Agent", BASE_HEADERS["User-Agent"])


def _browser_credentials_for_source(source_type: str) -> BrowserCredentials | None:
    prefix = source_type.upper()
    username = os.getenv(f"{prefix}_BROWSER_USERNAME")
    password = os.getenv(f"{prefix}_BROWSER_PASSWORD")
    if username and password:
        return BrowserCredentials(username=username, password=password)
    return None


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
        url = _rewrite_sciencedirect_url(url)
        headers["Referer"] = "https://www.sciencedirect.com/"
    elif journal.source_type == "informs":
        headers["Referer"] = "https://pubsonline.informs.org/"
    elif journal.source_type == "nber":
        headers["Referer"] = "https://www.nber.org/"
    cookies = _cookies_for_source(journal.source_type)
    return FetchRequest(url=url, headers=headers, cookies=cookies)


def _rewrite_wiley_url(url: str) -> str:
    if "onlinelibrary.wiley.com" not in url:
        return url
    clean = url.split("?", 1)[0]
    marker = "/doi/"
    if marker in clean and "/doi/abs/" not in clean and "/doi/full/" not in clean:
        return clean.replace(marker, "/doi/abs/", 1)
    return clean


def _cookies_for_source(source_type: str) -> dict[str, str] | None:
    env_key = COOKIE_ENV_MAP.get(source_type)
    if not env_key:
        return None
    cookie_text = os.getenv(env_key)
    if not cookie_text:
        return None
    return _parse_cookie_header(cookie_text)


def _parse_cookie_header(value: str) -> dict[str, str]:
    cookies: dict[str, str] = {}
    cleaned = value.strip().strip("\"'")
    for chunk in cleaned.split(";"):
        trimmed = chunk.strip()
        if not trimmed:
            continue
        if "=" not in trimmed:
            continue
        name, cookie_value = trimmed.split("=", 1)
        cookies[name.strip().strip('\"\'')] = cookie_value.strip().strip('\"\'')
    return cookies


def _parse_header_mapping(value: str) -> dict[str, str]:
    cleaned = value.strip()
    if not cleaned:
        return {}
    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            return {str(key): str(val) for key, val in data.items()}
    except json.JSONDecodeError:
        pass
    return _parse_cookie_header(cleaned)


def _browser_wait_selector_for_source(source_type: str) -> str | None:
    return {
        "sciencedirect": "script#__NEXT_DATA__",
    }.get(source_type)


def _rewrite_sciencedirect_url(url: str) -> str:
    if "www.sciencedirect.com" not in url:
        return url
    marker = "/science/article/abs/pii/"
    if marker in url:
        return url.replace(marker, "/science/article/pii/", 1)
    return url


def _browser_extract_script_for_source(source_type: str) -> str | None:
    return {
        "sciencedirect": "window.__NEXT_DATA__",
    }.get(source_type)


def _browser_init_scripts_for_source(source_type: str) -> list[str]:
    scripts: list[str] = []
    if source_type == "sciencedirect":
        scripts.append(_SCIDIR_FINGERPRINT_SCRIPT)
    env_value = os.getenv(f"{source_type.upper()}_BROWSER_INIT_SCRIPT")
    if env_value:
        path = Path(env_value)
        if path.exists():
            scripts.append(path.read_text(encoding="utf-8"))
        else:
            scripts.append(env_value)
    return scripts


def _browser_local_storage_for_source(source_type: str) -> dict[str, str] | None:
    raw = os.getenv(f"{source_type.upper()}_BROWSER_LOCAL_STORAGE")
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        LOGGER.warning("Invalid %s local storage JSON", source_type)
        return None
    if not isinstance(data, dict):
        LOGGER.warning("Local storage JSON for %s must be an object", source_type)
        return None
    return {str(key): str(value) for key, value in data.items()}


def _browser_user_data_dir_for_source(source_type: str) -> str | None:
    return os.getenv(f"{source_type.upper()}_USER_DATA_DIR")


def _local_storage_script(entries: dict[str, str]) -> str:
    payload = json.dumps(entries)
    return f"(() => {{ const entries = {payload}; Object.entries(entries).forEach(([k, v]) => localStorage.setItem(k, v)); }})()"


def _browser_headless_for_source(source_type: str) -> bool:
    value = os.getenv(f"{source_type.upper()}_BROWSER_HEADLESS")
    if value is None:
        return True
    return value.strip().lower() not in {"0", "false", "no"}


def _browser_launch_overrides(source_type: str) -> tuple[str | None, str | None]:
    prefix = source_type.upper()
    channel = os.getenv(f"{prefix}_BROWSER_CHANNEL")
    executable = os.getenv(f"{prefix}_BROWSER_EXECUTABLE")
    if channel and executable:
        raise BrowserLaunchConfigurationError(
            f"{source_type} browser sampling cannot set both {prefix}_BROWSER_CHANNEL and "
            f"{prefix}_BROWSER_EXECUTABLE; choose one."
        )
    normalized_channel = channel.strip() if channel and channel.strip() else None
    normalized_executable = None
    if executable and executable.strip():
        normalized_executable = str(Path(executable.strip()).expanduser())
    return normalized_channel, normalized_executable


def _require_sciencedirect_profile(user_data_dir: str | None) -> str:
    if not user_data_dir:
        raise RuntimeError(
            "ScienceDirect sampling requires SCIENCEDIRECT_USER_DATA_DIR. "
            "Run `uv run econ-atlas samples scd-session warmup` first."
        )
    path = Path(user_data_dir).expanduser()
    if not path.exists():
        raise RuntimeError(
            f"ScienceDirect profile directory '{path}' is missing. "
            "Re-run `samples scd-session warmup` to refresh the session."
        )
    return str(path)


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
        "ScienceDirect did not expose window.__NEXT_DATA__; "
        "rerun the warmup command and try again with --sdir-debug for clues."
    )
    artifacts = _scd_debug_artifacts(debug_dir, debug_label)
    if artifacts:
        joined = ", ".join(artifacts)
        message = f"{message} Debug files: {joined}"
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


_SCIDIR_FINGERPRINT_SCRIPT = """
(() => {
  Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
  window.chrome = window.chrome || { runtime: {} };
  const originalPlugins = navigator.plugins;
  Object.defineProperty(navigator, 'plugins', {
    get: () => originalPlugins || [1, 2, 3],
  });
  const languages = navigator.languages;
  Object.defineProperty(navigator, 'languages', {
    get: () => languages || ['en-US', 'en']
  });
})();
"""
COOKIE_ENV_MAP = {
    "wiley": "WILEY_COOKIES",
    "oxford": "OXFORD_COOKIES",
    "sciencedirect": "SCIENCEDIRECT_COOKIES",
    "chicago": "CHICAGO_COOKIES",
    "informs": "INFORMS_COOKIES",
    "nber": "NBER_COOKIES",
}

PROTECTED_SOURCE_TYPES = frozenset({"wiley", "oxford", "sciencedirect", "chicago", "informs"})
