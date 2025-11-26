"""
英文导入入口：封装 5_samples 包。
"""

from __future__ import annotations

from typing import Any, cast

from econatlas._loader import load_local_module

_pkg = cast(Any, load_local_module(__file__, "5_samples/__init__.py", "econatlas._samples_pkg"))

SampleCollector = _pkg.SampleCollector
SampleCollectorReport = _pkg.SampleCollectorReport
JournalSampleReport = _pkg.JournalSampleReport
BrowserLaunchConfigurationError = _pkg.BrowserLaunchConfigurationError
PlaywrightFetcher = _pkg.PlaywrightFetcher
BrowserCredentials = _pkg.BrowserCredentials
build_browser_headers = _pkg.build_browser_headers
browser_credentials_for_source = _pkg.browser_credentials_for_source
browser_user_agent_for_source = _pkg.browser_user_agent_for_source
browser_wait_selector_for_source = _pkg.browser_wait_selector_for_source
browser_extract_script_for_source = _pkg.browser_extract_script_for_source
browser_init_scripts_for_source = _pkg.browser_init_scripts_for_source
browser_local_storage_for_source = _pkg.browser_local_storage_for_source
browser_user_data_dir_for_source = _pkg.browser_user_data_dir_for_source
browser_headless_for_source = _pkg.browser_headless_for_source
browser_launch_overrides = _pkg.browser_launch_overrides
cookies_for_source = _pkg.cookies_for_source
rewrite_sciencedirect_url = _pkg.rewrite_sciencedirect_url
require_sciencedirect_profile = _pkg.require_sciencedirect_profile
local_storage_script = _pkg.local_storage_script
SourceInventory = _pkg.SourceInventory
JournalInventory = _pkg.JournalInventory
build_inventory = _pkg.build_inventory

__all__ = [
    "SampleCollector",
    "SampleCollectorReport",
    "JournalSampleReport",
    "BrowserLaunchConfigurationError",
    "PlaywrightFetcher",
    "BrowserCredentials",
    "build_browser_headers",
    "browser_credentials_for_source",
    "browser_user_agent_for_source",
    "browser_wait_selector_for_source",
    "browser_extract_script_for_source",
    "browser_init_scripts_for_source",
    "browser_local_storage_for_source",
    "browser_user_data_dir_for_source",
    "browser_headless_for_source",
    "browser_launch_overrides",
    "cookies_for_source",
    "rewrite_sciencedirect_url",
    "require_sciencedirect_profile",
    "local_storage_script",
    "SourceInventory",
    "JournalInventory",
    "build_inventory",
]
