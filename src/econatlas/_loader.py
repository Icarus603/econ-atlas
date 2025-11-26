"""
加载带数字/中文文件名的模块辅助工具。
"""

from __future__ import annotations

from importlib import util
from importlib.machinery import SourceFileLoader
from pathlib import Path
from types import ModuleType
import sys


def load_local_module(pkg_file: str, filename: str, alias: str) -> ModuleType:
    """
    从与 pkg_file 同目录下加载 filename，并用 alias 作为模块名返回。
    适用于文件名包含数字/中文的情况。
    """
    path = Path(pkg_file).parent / filename
    loader = SourceFileLoader(alias, str(path))
    spec = util.spec_from_loader(alias, loader)
    if spec is None or spec.loader is None:
        raise ImportError(f"无法加载模块 {filename}")
    module = util.module_from_spec(spec)
    sys.modules[alias] = module
    loader.exec_module(module)
    return module
