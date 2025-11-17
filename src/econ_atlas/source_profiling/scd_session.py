from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

DEFAULT_WARMUP_PROFILE_DIR = Path(".cache/econ-atlas/scd-profile")
DEFAULT_SCIENCEDIRECT_URL = "https://www.sciencedirect.com/"
DEFAULT_WARMUP_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)


def warmup_sciencedirect_profile(
    *,
    profile_dir: Path,
    target_url: str,
    wait_callback: Callable[[], None],
    export_local_storage: Path | None = None,
    user_agent: str | None = None,
) -> None:
    """Launch a headed persistent Chromium session so operators can pass Cloudflare challenges."""
    profile_dir = profile_dir.expanduser()
    profile_dir.mkdir(parents=True, exist_ok=True)
    if export_local_storage:
        export_local_storage = export_local_storage.expanduser()
        export_local_storage.parent.mkdir(parents=True, exist_ok=True)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover - import guard
        raise RuntimeError(
            "Playwright is required for warmup. Run `uv add playwright` and `uv run playwright install chromium`."
        ) from exc

    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            str(profile_dir),
            headless=False,
            user_agent=user_agent or DEFAULT_WARMUP_USER_AGENT,
        )
        page = context.new_page()
        page.goto(target_url, wait_until="domcontentloaded")
        try:
            wait_callback()
            if export_local_storage:
                raw_json = page.evaluate("JSON.stringify(window.localStorage)")
                payload: dict[str, str] = json.loads(raw_json) if raw_json else {}
                export_local_storage.write_text(
                    json.dumps(payload, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
        finally:
            context.close()
