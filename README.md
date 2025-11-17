# econ-atlas

Automated economics-literature harvesting · DeepSeek 翻译 · JSON 档案。

---

## 项目简介
econ-atlas 是一个自动化抓取项目，负责监控 `list.csv` 中列出的经济/管理学术期刊。CLI 会逐一读取 RSS，统一格式化条目、调用 DeepSeek API 将非中文摘要翻译为简体中文，并把结果按期刊写入 `data/<journal-slug>.json` 以供后续分析。

### 目标
- **自动化采集**：把所有期刊统一放入计划任务，避免手工抓取。
- **双语摘要**：保留原文摘要，并附带自动翻译的中文版，为后续中文综述提供素材。
- **可回溯档案**：每本期刊对应一个 JSON 文件，追加历史条目，方便审计与下游复现。

### 当前状态
- ✅ CLI 基架完成（`uv run econ-atlas crawl`），支持一次性运行与简单调度。
- ✅ RSS 采集 + DeepSeek 翻译 + JSON 存储流程已实现。
- ✅ `data/` 中的档案采用原子写入并保留翻译元数据。
- 🚧 后续计划：缺字段期刊的补抓、监控告警、打包/部署方案。

## 代码结构
- `list.csv`：期刊清单，记录名称、RSS、`source_type`（如 `cnki`、`wiley`、`sciencedirect`）。
- `src/econ_atlas/`：Python 业务代码（CLI、采集、翻译、存储等模块）。
- `samples/`：由 `samples collect` 生成的 HTML/JSON 样本（git 忽略）。
- `docs/parser_profiles/`：解析文档，列出各出版社 DOM 结构与注意事项。
- `openspec/`：OpenSpec 提案与规格。
- `tests/`：单元测试。

## 环境与测试
```bash
uv sync
cp .env.example .env
echo "DEEPSEEK_API_KEY=sk-..." >> .env
# 可选：配置 Elsevier API（推荐，用于 ScienceDirect API enrichment）
echo "ELSEVIER_API_KEY=sk-elsevier-..." >> .env

uv run ruff check . --fix
uv run mypy .
uv run pytest -q
```

## CLI 用法
- 单次抓取：`uv run econ-atlas crawl --once`
- 持续运行（默认 7 天轮询）：`uv run econ-atlas crawl`
- 重要参数：`--list-path`、`--output-dir`、`--interval`、`--verbose`

### 样本采集
```bash
uv run econ-atlas samples collect --include-source wiley --limit 3
uv run econ-atlas samples inventory --pretty
uv run econ-atlas samples import sciencedirect journal-slug ~/Downloads/article.html --entry-id manual
```
采集命令会在 `samples/<source_type>/<journal-slug>/` 下存储 HTML，配合 `docs/parser_profiles/*` 进行解析记录。

### 样本解析（ScienceDirect fallback）
```bash
uv run econ-atlas samples parse sciencedirect --input samples/sciencedirect --output tmp/scd.json
```
解析命令会遍历 `samples/sciencedirect/**/*/*.html`，调用 fallback DOM parser 抽取标题、作者、DOI/PII、摘要、关键字/Highlights 及 PDF 链接，打印覆盖率并在任何必填字段缺失或解析失败时退出非零。
`--output` 可写出 JSON 报告（包含缺失原因），便于在 CI/PR 中审查。

目前只有 ScienceDirect 走官方 API，其它来源（Wiley、Oxford、Chicago、INFORMS 等）仍依赖 Playwright/DOM parser，因此需要定期 warmup profile/cookies 并关注 DOM 改动。配置 `ELSEVIER_API_KEY` 后，`econ-atlas crawl` 会优先调用 Elsevier API 获取结构化标题/作者/摘要；若 API 不可用则退回 DOM（此时仍需提前运行 `samples scd-session warmup` 并在 `.env` 配好 `SCIENCEDIRECT_USER_DATA_DIR`、`SCIENCEDIRECT_COOKIES` 等参数）。无论 API 或 fallback 失败都会记录警告但不会中断任务。

### 受保护站点
Wiley、Oxford、ScienceDirect、Chicago、INFORMS 等站点由 Cloudflare/Akamai 保护，必须通过 Playwright 的 Chromium 才能稳定抓取。请先安装浏览器：
```bash
uv run playwright install chromium
```
`.env` 可提供 `*_COOKIES`、`*_BROWSER_USER_AGENT`、`*_BROWSER_HEADERS`、`*_BROWSER_USERNAME/PASSWORD`，CLI 会在浏览器打开前注入。为了让 Playwright 与真实 Chrome 指纹一致，还可以设置：
```
WILEY_BROWSER_CHANNEL=chrome
SCIENCEDIRECT_BROWSER_EXECUTABLE=/Applications/Google\ Chrome.app/...
```

> **注意**：除 ScienceDirect 之外的各出版社（Wiley、Oxford、Chicago、INFORMS 等）目前均 **没有** 官方 TDM/API，我们只能依赖 Playwright + DOM parser。生产环境请定期运行 `samples <source> warmup` 更新 profile、关注 `samples parse` 的字段覆盖； crawler 在这些来源上写入的仍是 RSS/DOM 解析结果，无法做到像 API 那样绝对稳定。

## ScienceDirect 现状
- 2025-11 的站点观测仍表明页面缺失 `__NEXT_DATA__`，因此 **crawler 默认使用 Elsevier Article Retrieval API**。只有在 API key 缺失或请求失败时，才会退回旧的 DOM fallback。
- `samples collect --include-source sciencedirect` 依旧会尝试 Playwright 抓 HTML（用于调试/回归），但由于 `__NEXT_DATA__` 缺失，只能保存 fallback 页面；这是预期行为。

### 使用 Elsevier API（推荐路径）
1. 在 `.env` 中配置 `ELSEVIER_API_KEY`（若出版社要求，还需 `ELSEVIER_INST_TOKEN`）。
2. 运行 `uv run econ-atlas crawl`，日志若没有 “falling back to DOM” 提示，即表示 API 已成功获取标题/作者/摘要。
3. API 有速率限制，crawler 内置简单重试；若超过配额会记录 warning，并在必要时自动切换到 DOM fallback。

### DOM fallback / 会话预热（仅在 API 不可用或采集样本时需要）
```bash
uv run econ-atlas samples scd-session warmup \
  --profile-dir .cache/econ-atlas/scd-profile \
  --pii S0047272725001975 \
  --export-local-storage .cache/econ-atlas/scd-localstorage.json
```
- 该命令会启动可视化 Chromium，让用户手工通过 Cloudflare/登录，并把 profile 路径写入 `.env`（`SCIENCEDIRECT_USER_DATA_DIR`）。
- 由于 `window.__NEXT_DATA__` 缺失，fallback 只会得到 “abs” 预览 HTML，但仍可用来调试 parser；相关 selector 记录在 `docs/parser_profiles/sciencedirect.md`。

## 输出
每本期刊会生成一个 `data/<journal-slug>.json`，包含元数据、历史条目、翻译结果与拉取时间。文件采用追加式写入，便于版本管理与下游系统使用。

## 后续规划
1. 针对缺字段期刊增加网页补抓，并争取更多出版社提供官方 API。
2. 增强监控/重试/告警能力，便于部署到 cron/systemd。
3. 提供 pipx / Docker 安装方式，允许切换翻译服务或离线模型。

若要贡献新解析器或采集能力，请先阅读 `docs/parser_profiles/*` 与 `openspec/` 中的提案，确保流程与文档同步更新。
