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

针对 ScienceDirect 可以开启调试：

```bash
uv run econ-atlas samples collect --include-source sciencedirect --limit 1 --sdir-debug
```

调试开启后会把截图与元数据写入 `samples/_debug_sciencedirect/`，方便排查 Cloudflare/Akamai 拦截。

若在浏览器中手工保存了 HTML/JSON，也可以导入：

```bash
uv run econ-atlas samples import sciencedirect journal-slug ~/Downloads/article.html --entry-id manual
```

文件会被复制到 `samples/sciencedirect/<journal-slug>/manual.html`，便于 parser 回归使用。

查看每个出版社/期刊已经有哪些样本：
```bash
uv run econ-atlas samples inventory --pretty
```
`samples inventory` 支持 `--format csv`，会输出每个 `source_type` 的样本数量、最新抓取时间以及手工备注（如“RSS 仍被 Cloudflare 拦截”），方便追踪遗漏的出版社。

Wiley、Oxford、ScienceDirect、Chicago、INFORMS 等高防护站点需要借助 Playwright + Chromium 通过浏览器模式获取 HTML。首次运行前请安装浏览器依赖：
```bash
uv run playwright install chromium
```
可在 `.env` 中配置 `WILEY_COOKIES`、`OXFORD_COOKIES` 等 Cookie 变量，以及 `*_BROWSER_USERNAME`/`*_BROWSER_PASSWORD` 形式的 HTTP 凭证，浏览器采样器会在打开页面前自动注入。如果站点还要求特定的 UA/Headers，可继续设置 `*_BROWSER_USER_AGENT` 以及 `*_BROWSER_HEADERS`（JSON 格式，键为 Header 名，值为字符串，例如 `{"Accept-Language":"zh-HK,...","sec-ch-ua":"\\"Chromium\\";v=\\"142\\""}`），就能让 Playwright 与真实浏览器完全一致。命令结束时会打印浏览器模式的成功/失败统计方便排查。

ScienceDirect 额外支持：
- `SCIENCEDIRECT_USER_DATA_DIR`：指向你本地 Chrome/Chromium profile，复用手工通过 Cloudflare 的 session。
- `SCIENCEDIRECT_BROWSER_INIT_SCRIPT`：自定义或文件路径，内容会在每次启动时注入（可伪装 `navigator.webdriver`、`chrome.runtime` 等）。
- `SCIENCEDIRECT_BROWSER_LOCAL_STORAGE`：JSON 对象，会在导航前写入 `localStorage`（例如 Optanon 或 TDM 凭证）。
- `SCIENCEDIRECT_BROWSER_HEADLESS`：设为 `false` 可在调试 Cloudflare 时以可视窗口运行 Chromium，默认 `true`。

采样器会把页面中的 `window.__NEXT_DATA__` 保存到 `<pre id="browser-snapshot-data">`，即便 DOM 没渲染也能让 parser 直接消费结构化数据。
> ⚠️ Chicago / INFORMS 的 RSS 接口由 Cloudflare 严格防护。即使用 Playwright 和文章页面复制的 Cookie，也可能只拿到 “Just a moment...” HTML，导致无法保存样本。只有在成功访问 RSS 时抓取到对应 Cookie 或使用其他数据源/API 才能继续采样。

### DOM 逆向与解析记录
1. **定位样本**：运行 `samples inventory` 获取当前覆盖情况，再进入 `samples/<source_type>/<slug>/` 打开 HTML。
2. **记录 selector**：在浏览器里加载本地 HTML（建议使用 DevTools 的 `Elements` 面板或 VS Code 的 “HTML Preview”），针对标题、作者、DOI、摘要、关键词/JEL、PDF 链接等字段，写下稳定的 CSS/XPath 或 JSON 路径。
3. **同步文档**：把结论写入 `docs/parser_profiles/<source_type>.md`。文件中的表格需要覆盖所有必填字段（Title、Authors、Affiliations、DOI、Publication date、Abstract、Keywords/JEL、PDF link），并说明所需 Cookie/Headers、是否需要点击“Read more”等操作。
4. **校验**：`pytest` 会自动检查每个 `source_type` 是否已有对应文档以及所有字段是否填写。当添加新样本或引入新出版社时，务必先补充文档再提交代码。
5. **与 Playwright 关系**：Playwright 只负责拿到干净的 HTML/JSON，解析器逻辑完全脱离浏览器。文档越详细，parser 越容易在离线样本上反复回归测试。

## 产出文件
- 每本期刊对应 `data/<journal-slug>.json`，包含期刊信息、历史条目、翻译状态、抓取时间等。
- 文件采用原子写入，可直接进入版本管理或供其他系统（可视化、搜索引擎等）使用。

## 后续规划（简要）
1. 针对缺少摘要或作者的期刊增加网页抓取补全。
2. 增加监控、重试、告警机制，方便部署到 cron/systemd。
3. 提供 pipx、Docker 等易安装包，并支持更多翻译方式（如离线模型）。
