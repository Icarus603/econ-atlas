<h1 align="center">econ-atlas（中文说明）</h1>

<p align="center">
  自动抓取 · 双语摘要 · JSON 历史库
</p>

---

econ-atlas 是一个自动化项目，用于维护 `list.csv` 中列出的经管期刊。Python CLI 会读取每个 RSS 源，规范化文章元数据，将非中文摘要通过 DeepSeek API 翻译为简体中文，并把结果以“每本期刊一个 JSON 文件”的形式存档，方便后续分析。

## 项目目标
- **自动化采集**：按可配置周期（默认每周）抓取所有 RSS 来源，减少人工筛查。
- **摘要双语化**：保留原文摘要，同时提供自动翻译的中文版本，方便中文语境下的文献综述。
- **历史归档**：每本期刊生成一个 JSON 历史库，保留之前抓取的论文，便于追踪与复现。

## 当前进度
- ✅ CLI 已成型，可运行一次 (`uv run econ-atlas crawl --once`) 或常驻调度。
- ✅ 已实现 RSS 解析、语言检测、DeepSeek 翻译及异常处理。
- ✅ 存储层会把结果写入 `data/` 目录下的 JSON，并进行去重与原子写入。
- 🚧 后续计划：完善告警/监控、处理缺摘要期刊、提供更易部署的打包方式、对接生产级调度。

## 代码结构
- `list.csv`: 期刊及 RSS 链接清单。
- `src/econ_atlas/`: CLI、配置、抓取、翻译、存储等核心模块。
- `openspec/`: 使用 OpenSpec 进行需求、设计与规格文档管理。
- `tests/`: 配置、CSV 解析、存储等单元测试。

## 快速开始
1. 安装依赖（使用 [uv](https://github.com/astral-sh/uv)）：
   ```bash
   uv sync
   ```
2. 复制环境变量模板并填入 DeepSeek API Key：
   ```bash
   cp .env.example .env
   echo "DEEPSEEK_API_KEY=sk-..." >> .env
   ```
3. 运行基础检查：
   ```bash
   uv run ruff check . --fix
   uv run mypy .
   uv run pytest -q
   ```

## CLI 用法
- 手动一次性运行：
  ```bash
  uv run econ-atlas crawl --once
  ```
- 按默认周期（7 天）循环运行：
  ```bash
  uv run econ-atlas crawl
  ```
- 常用参数：
- `--list-path PATH`：指定 CSV 清单（默认 `list.csv`）
- `--output-dir PATH`：JSON 输出目录（默认 `data/`）
- `--interval 12h` 或 `--interval-seconds 43200`：自定义间隔
- `--verbose/-v`：输出更详细的日志

开发环境会自动加载 `.env`，部署到生产时请通过系统环境变量或密钥管理工具提供 `DEEPSEEK_API_KEY`。

### HTML 样本采集

用于解析器开发的 DOM 样本可以通过以下命令获取：
```bash
uv run econ-atlas samples collect --limit 3 --include-source wiley --include-source oxford
```
命令会读取 `list.csv`，过滤指定的 `source_type`，抓取 RSS 中的条目并保存 HTML 到 `samples/<source_type>/<journal-slug>/`。

Wiley、Oxford、ScienceDirect、Chicago、INFORMS 等高防护站点需要借助 Playwright + Chromium 通过浏览器模式获取 HTML。首次运行前请安装浏览器依赖：
```bash
uv run playwright install chromium
```
可在 `.env` 中配置 `WILEY_COOKIES`、`OXFORD_COOKIES` 等 Cookie 变量，以及 `*_BROWSER_USERNAME`/`*_BROWSER_PASSWORD` 形式的 HTTP 凭证，浏览器采样器会在打开页面前自动注入，并在命令结束时输出浏览器模式的成功/失败统计。
> ⚠️ Chicago / INFORMS 的 RSS 接口由 Cloudflare 严格防护。即使用 Playwright 和文章页面复制的 Cookie，也可能只拿到 “Just a moment...” HTML，导致无法保存样本。只有在成功访问 RSS 时抓取到对应 Cookie 或使用其他数据源/API 才能继续采样。

## 产出文件
- 每本期刊对应 `data/<journal-slug>.json`，包含期刊信息、历史条目、翻译状态、抓取时间等。
- 文件采用原子写入，可直接进入版本管理或供其他系统（可视化、搜索引擎等）使用。

## 后续规划（简要）
1. 针对缺少摘要或作者的期刊增加网页抓取补全。
2. 增加监控、重试、告警机制，方便部署到 cron/systemd。
3. 提供 pipx、Docker 等易安装包，并支持更多翻译方式（如离线模型）。
