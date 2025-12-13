<h1 align="center">Econ-Atlas</h1>
<p align="center">你的文献地图——经管类顶刊一站式本地浏览</p>

## 你会得到什么
- `data/*.json`：每个期刊一个 JSON 归档（包含文章元数据、原摘要、语言检测、中文翻译与翻译状态）。
- `viewer/`：本地静态查看器（搜索/筛选/点开详情），通过本地 HTTP 服务打开阅读。

## 依赖与环境
- Python >= 3.11（建议使用 `uv` 管理依赖/虚拟环境）
- 部分来源需要 Playwright + 本地浏览器环境（详见下方环境变量）

## 快速开始
### 1) 安装
```bash
git clone https://github.com/Icarus603/econ-atlas.git
cd econ-atlas
uv sync
```
可选：如果你需要 Playwright 自带浏览器（不走本机 Chrome）：
```bash
uv run playwright install chromium
```

### 2) 配置环境变量（`.env`）
复制一份模板：
```bash
cp .env.example .env
```
按需填写（缺失会导致抓取/翻译失败）：
- 翻译（可选）：`DEEPSEEK_API_KEY`
- ScienceDirect API（可选）：`ELSEVIER_API_KEY`、`ELSEVIER_INST_TOKEN`
- 浏览器（抓取受保护站点时通常需要，强烈建议按自己机器填写）：
  - 二选一：`BROWSER_EXECUTABLE=<Chrome 路径>` 或 `BROWSER_CHANNEL=chrome`
  - `BROWSER_USER_AGENT`：从浏览器 DevTools 的 Network 请求头复制
  - `BROWSER_HEADERS`：从 DevTools 复制完整 Request Headers（JSON 或 cookie 形式都支持）
  - `BROWSER_USER_DATA_DIR`：持久化 profile（对 Cloudflare/登录态常有帮助）
  - `BROWSER_HEADLESS=true/false`
- Cookies（按来源可选）：`OXFORD_COOKIES`、`WILEY_COOKIES`、`CHICAGO_COOKIES`、`INFORMS_COOKIES`、`NBER_COOKIES`
- 节流/超时（秒，可选）：`*_THROTTLE_SECONDS`、`*_FETCH_TIMEOUT_SECONDS`、`TRANSLATION_THROTTLE_SECONDS`

### 3) 运行一次抓取
```bash
uv run econ-atlas crawl
```

## CLI 用法
### 抓取
- 全量抓取（含翻译，默认断点续跑）：`uv run econ-atlas crawl`
- 按来源抓取：`uv run econ-atlas crawl publisher oxford`
- 仅抓指定期刊：`uv run econ-atlas crawl --include-slug nber`
- 跳过翻译：任意抓取命令加 `--skip-translation`

### 样本（调试用）
- 采集 HTML 样本：`uv run econ-atlas samples collect --limit 3 --sdir-debug`
- 导出样本清单：`uv run econ-atlas samples inventory --format csv > samples.csv`

## 本地查看器（更好读）
查看器从 `data/*.json` 生成一个索引 `viewer/index.json`，浏览器据此加载期刊列表与统计。

```bash
# 启动本地服务（默认 127.0.0.1:8765）
uv run econ-atlas viewer serve --port 8765
```
浏览器打开：`http://127.0.0.1:8765/viewer/`

说明：
- `crawl` 默认会自动更新 `viewer/index.json`
- `viewer serve` 在 `index.json` 缺失时也会尝试自动生成（前提：仓库根目录下存在 `list.csv` 和 `data/`）

## 断点续跑与输出
- 断点续跑进度：默认写入 `.cache/crawl_progress.json`（删除即可全量重跑；可用 `--progress-path` 自定义）。
- 输出文件：`data/<slug>.json`（CNKI 为中文期刊名文件）。
- 运行日志：进入期刊打印 `开始 <期刊名>`；每篇条目打印 `期刊名 | 标题`；已完成条目显示“已完成，跳过”。

## macOS：用 launchd 常驻 + 定时运行
仓库内提供两份 `launchd` 模板（不提交个人路径），并提供脚本一键安装到本机：
- 模板：`launchd/*.plist.template`
- 安装：`launchd/install.sh`（生成并安装到 `~/Library/LaunchAgents/`）
- 卸载：`launchd/uninstall.sh`

安装（常驻 viewer + 每周日 08:00 定时 crawl）：
```bash
./launchd/install.sh --port 8765
```

仅安装常驻 viewer（不启用定时 crawl）：
```bash
./launchd/install.sh --port 8765 --no-crawl
```

卸载：
```bash
./launchd/uninstall.sh
```

注意：`launchd` 任务不会在机器睡眠时运行；如果你经常合盖，建议把定时点设在你通常开机/唤醒的时间段。模板中使用 `/usr/bin/caffeinate` 仅用于“任务启动后防止睡眠”，无法在机器已睡眠时强行启动任务。

## 目录速览
- `list.csv`：期刊列表（来源类型、RSS 链接等）
- `data/`：抓取产物（每刊一个 JSON）
- `viewer/`：本地静态查看器
- `src/econatlas/`：核心代码（feeds/crawlers/enrichers/translation/storage/samples + CLI）
- `tests/`：测试

## 开发与质量
```bash
uv run ruff check . --fix
uv run mypy .
uv run pytest -q
```

## 常见问题
- 查看器打不开 / 加载失败：必须通过 `http://` 打开（先运行 `uv run econ-atlas viewer serve`），不要直接双击 `viewer/index.html` 走 `file://`。
- ScienceDirect 增强没生效：检查 `ELSEVIER_API_KEY` / `ELSEVIER_INST_TOKEN` 是否设置。
- 翻译被跳过：确认未传 `--skip-translation` 且 `.env` 有 `DEEPSEEK_API_KEY`。
- 终端代理影响本地 curl：如果 `http_proxy` 指向本地代理，测试本地服务可用 `curl --noproxy '*' http://127.0.0.1:8765/viewer/`。
