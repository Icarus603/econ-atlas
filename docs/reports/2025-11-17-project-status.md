# econ-atlas 项目状态（2025-11-17）

## 1. 总览
- CLI 入口：`src/econ_atlas/cli.py` 暴露 `econ-atlas crawl/samples/...` 命令，基于 Typer。
- 核心 orchestrator：`src/econ_atlas/runner.py` 负责读取期刊列表、抓取 RSS、执行翻译/补全、存储 JSON 档案。
- 依赖管理：`pyproject.toml`（运行时包含 httpx、feedparser、Typer、Playwright、BeautifulSoup、pydantic 等）。

## 2. 数据流程
1. **列表与配置**：`list.csv` 通过 `JournalListLoader` (`src/econ_atlas/sources/list_loader.py`) 读取，生成 `JournalSource` 列表；CLI 启动时 `build_settings` (`src/econ_atlas/config.py`) 解析参数/环境（`DEEPSEEK_API_KEY`、`ELSEVIER_API_KEY` 等）。
2. **RSS 抓取**：`FeedClient` (`src/econ_atlas/ingest/feed.py`) 使用 httpx + feedparser 读取 RSS 或 JSON feeds，并支持特定源的 cookie/headers。受保护站点可通过 `PlaywrightFetcher` (`src/econ_atlas/source_profiling/browser_fetcher.py`) 获取。
3. **翻译**：`Runner._build_article` 中调用 DeepSeek 翻译器 (`src/econ_atlas/translate/deepseek.py`)，并记录 `TranslationRecord`。
4. **补全与持久化**：`JournalStore` (`src/econ_atlas/storage/json_store.py`) 负责 per-journal JSON 的去重/原子写入；新加的 `ScienceDirectEnricher` (`src/econ_atlas/sources/sciencedirect_enricher.py`) 在写入前补充字段（详见下文）。

## 3. 来源处理现状
- **ScienceDirect**：
  - 默认使用 Elsevier Article Retrieval API（`ScienceDirectApiClient` in `src/econ_atlas/sources/sciencedirect_api.py`）。
  - Enricher 先走 API，失败或缺 Key 时退回 DOM parser（`parse_sciencedirect_fallback`）。
  - `.env` 支持 `ELSEVIER_API_KEY`、`ELSEVIER_INST_TOKEN`；CLI 若缺 key 会打印警告但继续执行。
- **Wiley / Oxford / Chicago / INFORMS**：仍依赖 Playwright。`SampleCollector` (`src/econ_atlas/source_profiling/sample_collector.py`) 使用各自的 cookies/headers/用户数据目录；解析规则记录在 `docs/parser_profiles/<source>.md`。
- **Cambridge / NBER 等**：通过 `httpx` 直接抓取 HTML 或 JSON，不依赖浏览器。

## 4. 辅助工具与测试
- **samples 子命令**（`cli.py`）：支持 `collect`、`import`、`inventory`、`parse sciencedirect`，用于维护 parser 样本。
- **Parser Profile 文档**：`docs/parser_profiles/*.md` 记录 DOM selector、采样注意事项。
- **OpenSpec 变更**：历史记录位于 `openspec/changes`；最新的 API 切换方案已归档 (`changes/archive/2025-11-17-replace-sciencedirect-enricher-api/`) 并同步到 `openspec/specs/crawler-cli/spec.md`。
- **测试覆盖**：
  - `tests/test_sciencedirect_enricher.py`、`tests/test_runner_sciencedirect.py` 验证 API enrichment 和 Runner 集成。
  - 其它文件（如 `tests/test_sample_collector.py`, `tests/test_cli_samples.py`, `tests/test_storage.py` 等）覆盖采集、CLI、存储逻辑。
  - CI 推荐命令：`uv run ruff check . --fix`、`uv run mypy .`、`uv run pytest -q`。

## 5. 当前风险/差距
- **除 ScienceDirect 外均无官方 API**：Wiley、Oxford、Chicago、INFORMS 等仍依赖 Playwright 抓 DOM。没有 API 的站点很难做到 7x24 无人监管，一旦 Cloudflare、登录策略或 DOM 改动，就需要人工介入。
- **非 API 站点依赖 Playwright**：cookie/profile 过期或 DOM 变动会导致字段缺失；目前没有自动化告警。
- **会话维护手动**：`samples scd-session warmup` 等命令需要人工通过 Cloudflare；Chicago/INFORMS 等更频繁依赖人工介入。
- **字段覆盖监控有限**：只有日志和 `samples parse` 手动查看，缺少“连续 N 次缺字段”式的自动监测。
- **OUP/Chicago 等 DOM parser 尚未接入 Runner**：这些 parser 目前只在 `samples parse` 中使用，主流程仍写入 RSS 数据，是出于稳定性考虑（避免 Playwright 阻塞 crawler）。若未来要自动补齐，需要设计更完善的浏览器会话管理与错误隔离机制。

## 6. 建议的后续方向
1. **争取更多官方 API**：若能为 Wiley/Oxford/Chicago/INFORMS 获取 TDM API，可仿照 ScienceDirect 实现 API-based enricher。
2. **自动化会话助手**：编写脚本/命令自动导出 cookies/localStorage，减少 warmup 人工动作。
3. **字段监控**：在 `Runner` 中新增指标（例如某 journal 连续抓不到作者/摘要时触发告警），并或周期性执行 `samples parse` 生成报告。
4. **配置模板**：统一 `.env` 模板/脚本，降低新环境部署成本（目前 `.env.example` 已含关键变量，可继续完善注释）。

> 本文档基于 2025-11-17 的代码库状态，如需历史对比，可在 `docs/reports/` 中追加新日期的报告。
