"""
配置模块：负责解析 CLI 参数和环境变量，输出运行所需的 Settings。
文件夹采用英文命名，便于导入；内部提供中文注释说明用途。
"""

from __future__ import annotations

from .settings import Settings, SettingsError, build_settings, parse_interval

__all__ = ["Settings", "SettingsError", "build_settings", "parse_interval"]
