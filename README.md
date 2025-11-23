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
- 仅跑部分期刊：可附加 `--include-source sciencedirect --include-source wiley` 或 `--include-slug energy-economics`（对应 `data/<journal-slug>.json` 中的 slug），用逗号重复传参即可多选。

### 样本采集
```bash
uv run econ-atlas samples collect --include-source wiley --limit 3
uv run econ-atlas samples inventory --pretty
uv run econ-atlas samples import sciencedirect journal-slug ~/Downloads/article.html --entry-id manual
```
采集命令会在 `samples/<source_type>/<journal-slug>/` 下存储 HTML，配合 `docs/parser_profiles/*` 进行解析记录。

目前只有 ScienceDirect 走官方 API，其它来源（Wiley、Oxford、Chicago、INFORMS 等）尚未接入正文解析器，RSS 不含摘要时会留空。默认抓取会排除 Wiley/Chicago/INFORMS（三者需要浏览器会话且无 API）；如需包含这些来源，请显式传 `--include-source wiley --include-source chicago --include-source informs`。配置 `ELSEVIER_API_KEY` 后，`econ-atlas crawl` 会调用 Elsevier API 获取结构化标题/作者/摘要；若 API 缺失则跳过 ScienceDirect 丰富，不再尝试 DOM fallback。

## ScienceDirect 现状
- 2025-11 的站点观测仍表明页面缺失 `__NEXT_DATA__`，因此 **crawler 仅使用 Elsevier Article Retrieval API**。如果缺少 API key，将跳过 ScienceDirect 丰富，摘要可能缺失。
- `samples collect --include-source sciencedirect` 仍可用于调试/回归（抓 HTML 样本），但不在 crawler 中作为 fallback 使用。

### 使用 Elsevier API（推荐路径）
1. 在 `.env` 中配置 `ELSEVIER_API_KEY`（若出版社要求，还需 `ELSEVIER_INST_TOKEN`）。
2. 运行 `uv run econ-atlas crawl`，日志提示缺少 API key 时会跳过 ScienceDirect 丰富。
3. API 有速率限制，crawler 内置简单重试；若超过配额会记录 warning，不会再尝试 DOM fallback。

## 输出
每本期刊会生成一个 `data/<journal-slug>.json`，包含元数据、历史条目、翻译结果与拉取时间。文件采用追加式写入，便于版本管理与下游系统使用。

## 后续规划
1. 针对缺字段期刊增加网页补抓，并争取更多出版社提供官方 API。
2. 增强监控/重试/告警能力，便于部署到 cron/systemd。
3. 提供 pipx / Docker 安装方式，允许切换翻译服务或离线模型。

若要贡献新解析器或采集能力，请先阅读 `docs/parser_profiles/*` 与 `openspec/` 中的提案，确保流程与文档同步更新。
