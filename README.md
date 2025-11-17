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

## ScienceDirect 现状
> **实测（2025-11-17 17:30 GMT+8）**  
> - 访问 `https://www.sciencedirect.com/science/article/pii/S0047272725001975`。  
> - 使用系统 Chrome（或 `uv run econ-atlas samples scd-session warmup` 启动的 Chromium）并登录、手动通过 Cloudflare。  
> - 打开 DevTools Console 执行 `document.querySelector("script#__NEXT_DATA__") === null`，返回 `true`。  
> - Playwright CLI 运行 `uv run econ-atlas samples collect --include-source sciencedirect --limit 1 -v`，日志反复打印 `wait selector script#__NEXT_DATA__ timed out`，并只保存 fallback HTML。  
> - 该现象在默认 profile、项目专用 profile（`.cache/econ-atlas/scd-profile`）、不同出口（本地网络 / 手机热点）均复现。  
> 目前尚未找到官方公告或公开讨论确认页面结构的永久变动，上述结论仅代表我们的观测结果。

### 会话预热
```bash
uv run econ-atlas samples scd-session warmup \
  --profile-dir .cache/econ-atlas/scd-profile \
  --pii S0047272725001975 \
  --export-local-storage .cache/econ-atlas/scd-localstorage.json
```
命令会启动可视化 Chromium，让用户手工通过 Cloudflare/登录，再把 profile 路径写进 `.env`（`SCIENCEDIRECT_USER_DATA_DIR`）并提示是否复制 `localStorage`。

### 已知阻塞：`__NEXT_DATA__` 缺失
- **现象**：2025-11-17 仍可稳定复现 `window.__NEXT_DATA__` 缺失；DevTools 执行 `document.querySelector('script#__NEXT_DATA__')` 永远返回 `null`。
- **尝试过的方案**：真实 Chrome profile、`SCIENCEDIRECT_BROWSER_CHANNEL=chrome`、多次 warmup、切换 VPN/热点/出口、headed 模式人工辅助，全都只得到 `abs` 预览 HTML。
- **影响**：`samples collect --include-source sciencedirect` 会一直等待 `script#__NEXT_DATA__` 并超时，无法保存 JSON。
- **下一步**：
  1. 评估直接解析 fallback DOM（Article preview）。
  2. 申请 Elsevier TDM/API（参见 [Elsevier TDM Policy](https://www.elsevier.com/tdm/tdmrep-policy.json)），获取官方结构化数据。
  3. 在全新机器/网络重新验证是否还有环境能拿到 Next.js 页面，并记录可复现条件。

相关情况会持续记录在 `docs/parser_profiles/sciencedirect.md`。

## 输出
每本期刊会生成一个 `data/<journal-slug>.json`，包含元数据、历史条目、翻译结果与拉取时间。文件采用追加式写入，便于版本管理与下游系统使用。

## 后续规划
1. 针对缺字段期刊增加网页补抓。
2. 增强监控/重试/告警能力，便于部署到 cron/systemd。
3. 提供 pipx / Docker 安装方式，允许切换翻译服务或离线模型。

若要贡献新解析器或采集能力，请先阅读 `docs/parser_profiles/*` 与 `openspec/` 中的提案，确保流程与文档同步更新。
