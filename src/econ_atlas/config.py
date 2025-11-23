from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path


class SettingsError(RuntimeError):
    """Raised when CLI configuration is invalid."""


@dataclass(frozen=True)
class Settings:
    list_path: Path
    output_dir: Path
    interval: timedelta
    run_once: bool
    deepseek_api_key: str | None
    elsevier_api_key: str | None = None
    elsevier_inst_token: str | None = None
    include_slugs: set[str] | None = None
    include_sources: set[str] | None = None
    skip_translation: bool = False


_INTERVAL_RE = re.compile(r"^(?P<value>\d+)(?P<unit>[smhdw])$")
_UNIT_TO_SECONDS = {
    "s": 1,
    "m": 60,
    "h": 60 * 60,
    "d": 60 * 60 * 24,
    "w": 60 * 60 * 24 * 7,
}


def parse_interval(text: str | None, seconds_override: int | None) -> timedelta:
    """Convert CLI interval inputs into a timedelta."""
    if seconds_override is not None:
        if seconds_override <= 0:
            raise SettingsError("Interval seconds must be positive")
        return timedelta(seconds=seconds_override)

    if not text:
        return timedelta(days=7)

    match = _INTERVAL_RE.match(text.strip().lower())
    if not match:
        raise SettingsError(
            "Invalid interval. Use formats like '12h', '2d', '30m', or pass --interval-seconds."
        )

    value = int(match.group("value"))
    unit = match.group("unit")
    seconds = value * _UNIT_TO_SECONDS[unit]
    return timedelta(seconds=seconds)


def build_settings(
    *,
    list_path: Path,
    output_dir: Path,
    interval_text: str | None,
    interval_seconds: int | None,
    run_once: bool,
    include_slugs: set[str] | None,
    include_sources: set[str] | None,
    skip_translation: bool,
) -> Settings:
    """Validate CLI inputs and construct runtime settings."""
    list_path = list_path.expanduser()
    output_dir = output_dir.expanduser()
    if not list_path.exists():
        raise SettingsError(f"CSV list not found: {list_path}")

    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not skip_translation and not api_key:
        raise SettingsError("Missing DEEPSEEK_API_KEY. Add it to .env or the environment.")
    elsevier_key = os.getenv("ELSEVIER_API_KEY")
    elsevier_inst_token = os.getenv("ELSEVIER_INST_TOKEN")

    interval = parse_interval(interval_text, interval_seconds)
    return Settings(
        list_path=list_path,
        output_dir=output_dir,
        interval=interval,
        run_once=run_once,
        deepseek_api_key=api_key,
        elsevier_api_key=elsevier_key,
        elsevier_inst_token=elsevier_inst_token,
        include_slugs=include_slugs,
        include_sources=include_sources,
        skip_translation=skip_translation,
    )
