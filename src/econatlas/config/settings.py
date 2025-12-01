"""
配置解析模块：读取 CLI 传入的路径、过滤条件，并检查必要的环境变量。
保持英文命名以便导入，核心逻辑与现有行为兼容。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


class SettingsError(RuntimeError):
    """配置校验失败时抛出。"""


@dataclass(frozen=True)
class Settings:
    list_path: Path
    output_dir: Path
    deepseek_api_key: str | None
    elsevier_api_key: str | None = None
    elsevier_inst_token: str | None = None
    include_slugs: set[str] | None = None
    include_sources: set[str] | None = None
    skip_translation: bool = False


def build_settings(
    *,
    list_path: Path,
    output_dir: Path,
    include_slugs: set[str] | None,
    include_sources: set[str] | None,
    skip_translation: bool,
) -> Settings:
    """校验 CLI 入参并构建 Settings 对象。"""
    list_path = list_path.expanduser()
    output_dir = output_dir.expanduser()
    if not list_path.exists():
        raise SettingsError(f"CSV list not found: {list_path}")

    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not skip_translation and not api_key:
        raise SettingsError("Missing DEEPSEEK_API_KEY. Add it to .env or the environment.")
    elsevier_key = os.getenv("ELSEVIER_API_KEY")
    elsevier_inst_token = os.getenv("ELSEVIER_INST_TOKEN")

    return Settings(
        list_path=list_path,
        output_dir=output_dir,
        deepseek_api_key=api_key,
        elsevier_api_key=elsevier_key,
        elsevier_inst_token=elsevier_inst_token,
        include_slugs=include_slugs,
        include_sources=include_sources,
        skip_translation=skip_translation,
    )
