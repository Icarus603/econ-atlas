<h1 align="center">econ-atlas</h1>
<p align="center">从期刊列表到可翻译的 JSON 档案：抓取 · 增强 · 翻译 · 存储</p>

概要
----
- 覆盖来源：CNKI / ScienceDirect / Oxford / Cambridge / Wiley / Chicago / INFORMS / NBER（`list.csv` 含 39 个 RSS 期刊，现均可跑）。
- 受保护站点：持久浏览器会话（Playwright）、可配置 Cookies/UA/Headers/本地存储，ScienceDirect 反指纹脚本。
- 增强与翻译：Elsevier API 补全元数据（ScienceDirect），DeepSeek 翻译摘要（可跳过）。
- CLI 能力：全量抓取、按出版商抓取、采集 HTML 样本、生成样本清单。

快速上手
--------
1) 安装环境  
- Python 3.11+，推荐 `uv sync`（锁文件 `uv.lock`）。

2) 配置 `.env`  
- 必填：`DEEPSEEK_API_KEY`；可选：`ELSEVIER_API_KEY`。  
- 全局浏览器（可选）：`BROWSER_EXECUTABLE`、`BROWSER_USER_AGENT`、`BROWSER_HEADERS`、`BROWSER_HEADLESS=true/false`、`BROWSER_USER_DATA_DIR`。  
- 节流（秒，可选，默认 3s）：`OXFORD_THROTTLE_SECONDS`、`WILEY_THROTTLE_SECONDS`、`CHICAGO_THROTTLE_SECONDS`、`INFORMS_THROTTLE_SECONDS`、`SCIENCEDIRECT_THROTTLE_SECONDS`。  
- 每站 Cookies（可选）：`OXFORD_COOKIES`、`WILEY_COOKIES`、`CHICAGO_COOKIES`、`INFORMS_COOKIES`。
- CNKI 首次建档：先用持久 profile 打开任意 CNKI 文章并手动通过安全验证：  
  ```bash
  /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
    --user-data-dir="$(pwd)/.cache/econ-atlas/profile" \
    --profile-directory=Default
  ```  
  完成验证码后再运行爬虫，避免被安全验证拦截。
  示例文章验证页：  
  https://kns.cnki.net/verify/home?captchaType=clickWord&ident=bc397c&captchaId=25a62995-1e07-4394-96a5-757247d5684d&returnUrl=iECBDnhr716Qd6pbb7El10nguP5Sbm9UQxpzsYxSAM-JuReIJajXtNdr2yG6yJzj8xtuLP3wd443vY_OaZyR0jT6sBJLsgoyNCTf0GcJaVUVOGk5y_xIRc9m7san12A_std8_2Z4w_8c8iJ045z2ryDxv9zkepG549CWjuNuQ9MVIjQ1k3sd2KzBMuKLHOnzYjmPX0FYYcmOn-fsXcjx8Un6mCZsWPlQb7XIPURuyV5PLb2htFL27zbYSeDNlemfQNGs7_Uihf7Ebo01Ui4RrTo3T544lG3kH2M_GOkYJKkT_Py_HVAVdWFHRKT_zn9pLhFGrLaSxQMXBKLvB1PQkZEYiP3KcOh_
  说明：Cambridge / ScienceDirect 走 API 或非 Playwright，不会遇到此验证码；目前使用 Playwright 的来源（Oxford/Wiley/Chicago/INFORMS/NBER/CNKI）仅 CNKI 可能触发此验证，其他来源暂未观察到。

3) 常用命令  
- 全量抓取：`uv run econ-atlas crawl --once --skip-translation`  
- 指定出版商：`uv run econ-atlas crawl publisher sciencedirect --once --skip-translation`  
- 采集样本：`uv run econ-atlas samples collect --limit 3 --sdir-debug`  
- 样本清单：`uv run econ-atlas samples inventory --format csv > samples.csv`

数据流
-----
- 列表解析：`list.csv` → `0.0_期刊列表.py` → `JournalSource`（slug/来源校验）。  
- 抓取：`FeedClient` 标准化 RSS/JSON；按来源路由至爬虫，Wiley/Chicago/INFORMS/Oxford 用浏览器补全，ScienceDirect 可走 Elsevier API。  
- 翻译：DeepSeek 处理非中文摘要（可 `--skip-translation`）。  
- 存储：`JournalStore` 合并/去重/排序，输出 `data/<slug>.json`（CNKI 保留中文文件名）。  
- 样本：`SampleCollector` 抓 HTML 到 `samples/`，可保存调试截图/trace。

目录导览
------
- `src/econatlas/0_feeds/`：列表解析、RSS/JSON 抓取与标准化。  
- `src/econatlas/1_crawlers/`：按来源爬虫（CNKI、ScienceDirect+Elsevier API、Oxford 持久会话、Cambridge、NBER、Wiley/Chicago/INFORMS 浏览器补全）。  
- `src/econatlas/2_enrichers/`：Elsevier API、Oxford 页面解析。  
- `src/econatlas/3_translation/`：翻译基类、DeepSeek 适配。  
- `src/econatlas/4_storage/`：档案合并与 JSON 写盘。  
- `src/econatlas/5_samples/`：浏览器抓取、样本采集、样本清单。  
- `src/econatlas/cli/app.py`：Typer CLI 入口；`config/settings.py`、`models.py`、`_loader.py`。

开发与校验
---------
- 代码风格：`uv run ruff check . --fix`  
- 类型检查：`uv run mypy .`  
- 测试：`uv run pytest -q`
