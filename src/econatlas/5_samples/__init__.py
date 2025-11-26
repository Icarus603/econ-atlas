"""
样本相关工具：采集、浏览器抓取与环境配置、样本清单。
目录采用英文编号，文件名为中文+编号，通过此处导出便于英文导入。
"""

from __future__ import annotations

from econatlas._loader import load_local_module

_collector = load_local_module(__file__, "5.1_样本采集.py", "econatlas._samples_collector")
_fetcher = load_local_module(__file__, "5.2_浏览器抓取.py", "econatlas._samples_fetcher")
_env = load_local_module(__file__, "5.3_浏览器环境.py", "econatlas._samples_env")
_inventory = load_local_module(__file__, "5.4_样本清单.py", "econatlas._samples_inventory")

SampleCollector = _collector.SampleCollector
SampleCollectorReport = _collector.SampleCollectorReport
JournalSampleReport = _collector.JournalSampleReport
BrowserLaunchConfigurationError = _collector.BrowserLaunchConfigurationError

PlaywrightFetcher = _fetcher.PlaywrightFetcher
BrowserCredentials = _fetcher.BrowserCredentials

build_browser_headers = _env.build_browser_headers
browser_credentials_for_source = _env.browser_credentials_for_source
browser_user_agent_for_source = _env.browser_user_agent_for_source
browser_wait_selector_for_source = _env.browser_wait_selector_for_source
browser_extract_script_for_source = _env.browser_extract_script_for_source
browser_init_scripts_for_source = _env.browser_init_scripts_for_source
browser_local_storage_for_source = _env.browser_local_storage_for_source
browser_user_data_dir_for_source = _env.browser_user_data_dir_for_source
browser_headless_for_source = _env.browser_headless_for_source
browser_launch_overrides = _env.browser_launch_overrides
cookies_for_source = _env.cookies_for_source
rewrite_sciencedirect_url = _env.rewrite_sciencedirect_url
require_sciencedirect_profile = _env.require_sciencedirect_profile
local_storage_script = _env.local_storage_script

SourceInventory = _inventory.SourceInventory
JournalInventory = _inventory.JournalInventory
build_inventory = _inventory.build_inventory

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
