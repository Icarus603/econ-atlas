<h1 align="center">econ-atlas</h1>

<p align="center">从期刊列表到可翻译的 JSON 档案：抓取、增强、翻译，一条龙 CLI。</p>

目录导航
--------
- [项目速览](#项目速览)
- [快速上手](#快速上手)
- [数据流与产出](#数据流与产出)
- [带序号的目录与文件](#带序号的目录与文件)
- [核心入口与其他文件](#核心入口与其他文件)
- [开发与校验](#开发与校验)

项目速览
--------
- 多来源：CNKI / ScienceDirect / Oxford / Cambridge / Wiley / Chicago / INFORMS / NBER。
- 受保护站点：内置浏览器采样、Cookies、UA、LocalStorage、反指纹脚本。
- 增强与翻译：Elsevier API 补全元数据，DeepSeek 翻译摘要。
- CLI：全量抓取、按出版商抓取、HTML 样本采集、样本清单。

快速上手
--------
- 环境：Python 3.11+（推荐 `uv`，锁文件 `uv.lock`）。
- 安装：`uv sync`
- 环境变量：必需 `DEEPSEEK_API_KEY`；可选 `ELSEVIER_API_KEY` / `ELSEVIER_INST_TOKEN`（ScienceDirect 增强）。
- 常用命令：
  - 全量抓取：`uv run econ-atlas crawl --once --skip-translation`
  - 指定来源：`uv run econ-atlas crawl publisher sciencedirect --once --skip-translation`
  - 样本采集：`uv run econ-atlas samples collect --limit 3 --sdir-debug`
  - 样本清单：`uv run econ-atlas samples inventory --format csv > samples.csv`

数据流与产出
-----------
- 期刊列表：`list.csv` → `0.0_期刊列表.py` → `JournalSource`。
- 抓取：`FeedClient`/爬虫从 RSS/JSON/浏览器获取条目；ScienceDirect 可选 Elsevier API 增强；Oxford 走浏览器补全作者。
- 翻译：DeepSeek 翻译非中文摘要（或 `--skip-translation` 跳过），状态写入 `TranslationRecord`。
- 存储：每个期刊一个 JSON 档案存放 `data/`，结构见 `src/econatlas/models.py`。
- 样本：`samples/` 存放原始 HTML；`samples/_debug_sciencedirect` 可含截图/trace/DOM。

带序号的目录与文件
------------------
- `src/econatlas/0_feeds/`
  - `0.0_期刊列表.py`：解析 CSV，校验来源、生成 slug，产出 `JournalSource`。
  - `0.1_RSS_抓取.py`：RSS/JSON 抓取与标准化，支持浏览器兜底、Cookies、作者/摘要解析与时间规范化。
- `src/econatlas/1_crawlers/`
  - `1.0_CNKI_爬虫.py`：基于标准化 feed 生成 `ArticleRecord`，语言检测 + 翻译占位。
  - `1.1_ScienceDirect_爬虫.py`：feed 拉取 + Elsevier API 增强（标题/作者/摘要）+ 占位翻译。
  - `1.2_Oxford_爬虫.py`：RSS 后浏览器补全作者（持久会话降低 Cloudflare），占位翻译。
  - `1.3_Cambridge_爬虫.py`：直接用 feed 数据，无额外增强。
- `src/econatlas/2_enrichers/`
  - `2.1_ScienceDirect_增强器.py`：Elsevier Article Retrieval API 封装，按 PII 合并作者/摘要/日期。
  - `2.2_Oxford_增强器.py`：Playwright 抓取 Oxford 页，解析 JSON-LD 与 meta 作者。
- `src/econatlas/3_translation/`
  - `3.1_翻译基础.py`：语言检测、翻译协议、占位/失败结果。
  - `3.2_DeepSeek_翻译.py`：DeepSeek Chat Completions API 适配，译为简体中文。
- `src/econatlas/4_storage/`
  - `4.1_JSON存储.py`：按期刊合并/去重/排序，优先成功翻译，写 JSON（CNKI 文件名保留中文）。
- `src/econatlas/5_samples/`
  - `5.1_样本采集.py`：选取 feed 条目，受保护来源走浏览器，校验 ScienceDirect 页面并存 HTML。
  - `5.2_浏览器抓取.py`：Playwright 抓取封装，支持持久 profile、截图、trace。
  - `5.3_浏览器环境.py`：浏览器启动/指纹配置，读取 Cookies/UA/LocalStorage/自定义脚本；含 ScienceDirect 反指纹与冲突校验。
  - `5.4_样本清单.py`：遍历 `samples/` 汇总来源/期刊样本数与最新时间，支持 JSON/CSV。

核心入口与其他文件
------------------
- `src/econatlas/cli/app.py`：Typer CLI，包含 `crawl`、`crawl publisher`、`samples collect/import/inventory`。
- `_loader.py`：动态加载含数字/中文文件名的模块，供封装入口使用。
- `config/settings.py`：解析 CLI 参数与环境变量（间隔、输出目录、API key、过滤）。
- `models.py`：Pydantic 模型（期刊、标准化 feed、文章、翻译、档案）。
- `tests/`：Pytest 覆盖 CLI 过滤、列表解析、存储合并、翻译占位等。

开发与校验
----------
- 代码检查：`uv run ruff check . --fix`
- 类型检查：`uv run mypy .`
- 测试：`uv run pytest -q`
- 常用环境变量（可写 `.env`）：
  - 翻译：`DEEPSEEK_API_KEY=...`
  - ScienceDirect 增强：`ELSEVIER_API_KEY=...`，`ELSEVIER_INST_TOKEN=...`
  - Cookies：`WILEY_COOKIES=...`、`CHICAGO_COOKIES=...`、`INFORMS_COOKIES=...`、`SCIENCEDIRECT_COOKIES=...`
  - 浏览器 Profile：`SCIENCEDIRECT_USER_DATA_DIR=/path/to/chrome-profile`
