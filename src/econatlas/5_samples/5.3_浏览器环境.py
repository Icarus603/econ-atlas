"""
浏览器环境配置：读取环境变量、组装 headers/cookies/UA 以及 ScienceDirect 特殊脚本。
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from econatlas._loader import load_local_module

_fetcher = load_local_module(__file__, "5.2_浏览器抓取.py", "econatlas._samples_fetcher")
BrowserCredentials = _fetcher.BrowserCredentials  # type: ignore[attr-defined]

LOGGER = logging.getLogger(__name__)


class BrowserLaunchConfigurationError(RuntimeError):
    """浏览器启动配置冲突时抛出。"""


BASE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

COOKIE_ENV_MAP = {
    "wiley": "WILEY_COOKIES",
    "oxford": "OXFORD_COOKIES",
    "sciencedirect": "SCIENCEDIRECT_COOKIES",
    "chicago": "CHICAGO_COOKIES",
    "informs": "INFORMS_COOKIES",
    "nber": "NBER_COOKIES",
}

SCIDIR_FINGERPRINT_SCRIPT = """
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


def build_browser_headers(headers: dict[str, str], source_type: str) -> dict[str, str]:
    merged = dict(BASE_HEADERS)
    merged.update(headers)
    extra = browser_headers_from_env(source_type)
    if extra:
        merged.update(extra)
    return merged


def browser_headers_from_env(source_type: str) -> dict[str, str] | None:
    raw = os.getenv("BROWSER_HEADERS")
    if not raw:
        return None
    parsed = parse_header_mapping(raw)
    return parsed or None


def browser_user_agent_for_source(source_type: str, headers: dict[str, str]) -> str:
    env_value = os.getenv("BROWSER_USER_AGENT")
    if env_value:
        return env_value.strip()
    return headers.get("User-Agent", BASE_HEADERS["User-Agent"])


def browser_credentials_for_source(source_type: str) -> BrowserCredentials | None:
    prefix = source_type.upper()
    username = os.getenv(f"{prefix}_BROWSER_USERNAME")
    password = os.getenv(f"{prefix}_BROWSER_PASSWORD")
    if username and password:
        return BrowserCredentials(username=username, password=password)
    return None


def cookies_for_source(source_type: str) -> dict[str, str] | None:
    env_key = COOKIE_ENV_MAP.get(source_type)
    if not env_key:
        return None
    cookie_text = os.getenv(env_key)
    if not cookie_text:
        return None
    return parse_cookie_header(cookie_text)


def parse_cookie_header(value: str) -> dict[str, str]:
    cookies: dict[str, str] = {}
    cleaned = value.strip().strip("\"'")
    for chunk in cleaned.split(";"):
        trimmed = chunk.strip()
        if not trimmed or "=" not in trimmed:
            continue
        name, cookie_value = trimmed.split("=", 1)
        cookies[name.strip().strip('\"\'')] = cookie_value.strip().strip('\"\'')
    return cookies


def parse_header_mapping(value: str) -> dict[str, str]:
    cleaned = value.strip()
    if not cleaned:
        return {}
    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            return {str(key): str(val) for key, val in data.items()}
    except json.JSONDecodeError:
        pass
    return parse_cookie_header(cleaned)


def browser_wait_selector_for_source(source_type: str) -> str | None:
    return {
        "sciencedirect": "script#__NEXT_DATA__",
    }.get(source_type)


def rewrite_sciencedirect_url(url: str) -> str:
    if "www.sciencedirect.com" not in url:
        return url
    marker = "/science/article/abs/pii/"
    if marker in url:
        return url.replace(marker, "/science/article/pii/", 1)
    return url


def browser_extract_script_for_source(source_type: str) -> str | None:
    return {
        "sciencedirect": "window.__NEXT_DATA__",
    }.get(source_type)


def browser_init_scripts_for_source(source_type: str) -> list[str]:
    scripts: list[str] = []
    if source_type == "sciencedirect":
        scripts.append(SCIDIR_FINGERPRINT_SCRIPT)
    env_value = os.getenv(f"{source_type.upper()}_BROWSER_INIT_SCRIPT")
    if env_value:
        path = Path(env_value)
        if path.exists():
            scripts.append(path.read_text(encoding="utf-8"))
        else:
            scripts.append(env_value)
    return scripts


def browser_local_storage_for_source(source_type: str) -> dict[str, str] | None:
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


def local_storage_script(entries: dict[str, str]) -> str:
    payload = json.dumps(entries)
    return "(() => { const entries = " + payload + "; Object.entries(entries).forEach(([k, v]) => localStorage.setItem(k, v)); })()"


def browser_user_data_dir_for_source(source_type: str) -> str | None:
    env_value = os.getenv("BROWSER_USER_DATA_DIR")
    if env_value:
        return env_value
    return None


def browser_headless_for_source(source_type: str) -> bool:
    value = os.getenv("BROWSER_HEADLESS")
    if value is None:
        return True
    return value.strip().lower() not in {"0", "false", "no"}


def browser_launch_overrides(source_type: str) -> tuple[str | None, str | None]:
    channel = os.getenv("BROWSER_CHANNEL")
    executable = os.getenv("BROWSER_EXECUTABLE")
    if channel and executable:
        raise BrowserLaunchConfigurationError(
            f"{source_type} 同时配置 BROWSER_CHANNEL 与 BROWSER_EXECUTABLE，需二选一。"
        )
    normalized_channel = channel.strip() if channel and channel.strip() else None
    normalized_executable = None
    if executable and executable.strip():
        normalized_executable = str(Path(executable.strip()).expanduser())
    return normalized_channel, normalized_executable


def require_sciencedirect_profile(user_data_dir: str | None) -> str:
    if not user_data_dir:
        raise RuntimeError(
            "ScienceDirect 采样需要 SCIENCEDIRECT_USER_DATA_DIR，提供一个有效的持久化 profile 路径。"
        )
    path = Path(user_data_dir).expanduser()
    if not path.exists():
        raise RuntimeError(f"ScienceDirect profile 目录缺失：{path}")
    return str(path)
