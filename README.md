<h1 align="center">Econ Atlas</h1>
<p align="center">抓取并翻译经管类顶刊，逐篇写盘为标准化 JSON，内置断点续跑。</p>


## 快速开始（3 步）
1) 克隆代码  
   ```bash
   git clone https://github.com/Icarus603/econ-atlas.git
   cd econ-atlas
   ```
2) 安装依赖（Python 3.11+，推荐 [uv](https://docs.astral.sh/uv/)）  
   ```bash
   uv sync
   # 浏览器安装：若用本机 Chrome（推荐），无需安装 Playwright 自带浏览器；
   # 只在你想用内置 Chromium 时执行：
   # uv run playwright install chromium
   # 想改用 Playwright 的稳定版 Chrome 则：
   # uv run playwright install chrome
   ```
3) 配置环境变量（必填，未填无法正常抓取）  
   创建 `.env`（或在环境中导出）并按本机填写：
   - 核心：`DEEPSEEK_API_KEY`（翻译用）  
   - 浏览器：**必填**，全部按自己机器填写（路径、UA、Headers、Profile）。  
     - 运行用哪个浏览器：填 `BROWSER_EXECUTABLE=<你的 Chrome 可执行路径>`，或用渠道 `BROWSER_CHANNEL=chrome`。路径请在本机找到对应二进制（示例仅供参考）。  
     - UA/请求头：打开目标站点 → 开发者工具（Windows/Linux：F12 或 Ctrl+Shift+I；macOS：Cmd+Option+I）→ Network → 任意请求 → Headers → 复制 `user-agent` 到 `BROWSER_USER_AGENT`，复制完整 Request Headers 到 `BROWSER_HEADERS`。  
     - 其他：`BROWSER_USER_DATA_DIR`（持久化 profile 目录）、`BROWSER_HEADLESS=true/false`。  
   - 可选：`ELSEVIER_API_KEY`、`ELSEVIER_INST_TOKEN`（ScienceDirect API 增强）  
   - 节流/超时（秒）：`OXFORD_THROTTLE_SECONDS`、`WILEY_THROTTLE_SECONDS`、`CHICAGO_THROTTLE_SECONDS`、`INFORMS_THROTTLE_SECONDS`、`SCIENCEDIRECT_THROTTLE_SECONDS`、`WILEY_FETCH_TIMEOUT_SECONDS`、`CHICAGO_FETCH_TIMEOUT_SECONDS`、`INFORMS_FETCH_TIMEOUT_SECONDS`  
   - Cookies（如需登录态）：`OXFORD_COOKIES`、`WILEY_COOKIES`、`CHICAGO_COOKIES`、`INFORMS_COOKIES`

## 运行方式
- 全量抓取（含翻译，默认断点续跑）：  
  ```bash
  uv run econ-atlas crawl
  ```
- 按来源抓取：`uv run econ-atlas crawl publisher oxford`
- 仅抓指定期刊 slug：`uv run econ-atlas crawl --include-slug nber`
- 跳过翻译：在任意抓取命令添加 `--skip-translation`
- 样本采集（抓页面 HTML 作调试）：`uv run econ-atlas samples collect --limit 3 --sdir-debug`
- 样本清单导出：`uv run econ-atlas samples inventory --format csv > samples.csv`

### 运行行为提示
- 断点续跑：进度写入 `.cache/crawl_progress.json`，删除即可全量重跑，可用 `--progress-path` 自定义。
- 输出：每篇期刊写入 `data/<slug>.json`，翻译结果也是逐篇落盘。
- 日志：进入期刊时打印 `开始 <期刊名>`；每篇 `期刊名 | 标题`；已完成项会显示“已完成，跳过”。

## 定时运行
项目不内置调度，可用 cron/systemd。示例：每周一 02:00 全量抓取（可按需添加 `--skip-translation` 或筛选来源/期刊）：
```cron
0 2 * * 1 cd /path/to/econ-atlas && uv run econ-atlas crawl >> crawl.log 2>&1
```

## 目录速览
- `src/econatlas/0_feeds/`：期刊列表解析、RSS/JSON 拉取与标准化。
- `src/econatlas/1_crawlers/`：各来源爬虫（Oxford/Cambridge/NBER/Wiley/Chicago/INFORMS 走 Playwright，ScienceDirect 可走 Elsevier API）。
- `src/econatlas/2_enrichers/`：页面/API 增强（NBER 摘要抽取、ScienceDirect API、元数据补全）。
- `src/econatlas/3_translation/`：翻译基类与 DeepSeek 适配（可切换成 NoOp）。
- `src/econatlas/4_storage/`：标准化 JSON 合并与写盘。
- `src/econatlas/5_samples/`：浏览器采样与样本清单工具。
- `src/econatlas/cli/app.py`：Typer CLI 入口；`config/settings.py` 处理参数与必填环境；`models.py` 定义数据模型。
- `list.csv`：期刊来源配置；`data/`：抓取产物；`tests/`：单元/集成测试。

## 常用参数（抓取子命令）
- `--include-source`：仅抓取指定来源类型（如 `sciencedirect`）。
- `--include-slug`：仅抓特定期刊（支持多次传入）。
- `--progress-path`：自定义断点续跑文件。

## 开发与质量
- 代码格式：`uv run ruff check . --fix`
- 类型检查：`uv run mypy .`
- 测试：`uv run pytest -q`
- Python >=3.11，使用 uv 虚拟环境；避免 print 调试，推荐日志。

## 常见问题
- 浏览器必填吗？是的，`.env` 需填你本机的浏览器可执行路径 + UA + Headers（从开发者工具复制）。只有在主动改用 Playwright 自带内核时才不需要这些值。
- 缺少浏览器内核：如果不用本机 Chrome，请先安装 Playwright 浏览器：`uv run playwright install chromium`（或 `uv run playwright install chrome`），并调整 `BROWSER_CHANNEL`/`BROWSER_EXECUTABLE` 指向它。
- ScienceDirect 增强未生效：检查 `ELSEVIER_API_KEY` / `ELSEVIER_INST_TOKEN` 是否设置。
- 翻译被跳过：确保未传 `--skip-translation` 且存在 `DEEPSEEK_API_KEY`。
