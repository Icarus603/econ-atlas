# ScienceDirect（Elsevier）

## 当前阻塞
- **推荐方案**：配置 `ELSEVIER_API_KEY`（以及必要的 inst token）后，crawler 会直接调用 Elsevier Article Retrieval API 获得结构化 JSON，不再依赖 `window.__NEXT_DATA__`。下述 DOM 说明仅在 API 不可用或作为回归测试时使用。
- `window.__NEXT_DATA__` 长期缺失：2025-11-17 17:30 (GMT+8) 复现；无论使用 CLI 预热的 `.cache/econ-atlas/scd-profile`，还是系统默认 Chrome profile，在 DevTools 执行 `document.querySelector('script#__NEXT_DATA__')` 都得到 `null`。即便手动通过 Cloudflare、人为输入 `/science/article/pii/...` 链接，ScienceDirect 仍返回 `abs` 版的静态 HTML，Playwright 抓不到 Next.js JSON。当前尚未找到公开资料确认结构调整，仅记录我们自己的观测。
- 已尝试方案：多次运行 `samples scd-session warmup`、复用真实 Chrome profile、强制 `SCIENCEDIRECT_BROWSER_CHANNEL=chrome`、切换 IP/热点/出口、开启 headed 模式手动协助加载，但都失败。
- 直接后果：`samples collect --include-source sciencedirect` 会在等待 `script#__NEXT_DATA__` 时超时，每篇文章都只留下 fallback HTML，没有结构化 JSON。

### 可能的解决方向
1. **解析 fallback DOM**：把 parser 调整成基于当前静态页面（`Article preview` 部分）抽取字段，不再依赖 JSON。
2. **接入 Elsevier TDM/API**：申请官方 key 并遵守 [Elsevier Text and Data Mining Policy](https://www.elsevier.com/tdm/tdmrep-policy.json)，直接拉结构化结果，绕过浏览器落地。
3. **准备全新环境**：在另一台机器或全新 profile + 出口上重新验证 `__NEXT_DATA__` 是否恢复，若某个组合能拿到 JSON，再复制 profile 给采样器（仅在 API 不可用时需要）。

## 样本与现状
- `samples/sciencedirect/journal-of-financial-economics/https-www-sciencedirect-com-science-article-pii-s0304405x25001251.html`
- `samples/sciencedirect/journal-of-public-economics/https-www-sciencedirect-com-science-article-pii-s0047272725001975.html`
- `samples/sciencedirect/journal-of-development-economics/https-www-sciencedirect-com-science-article-pii-s0304387825002263.html`
- `samples/sciencedirect/journal-of-economic-behavior-and-organization/https-www-sciencedirect-com-science-article-pii-s0167268125004238.html`
- `samples/sciencedirect/journal-of-environmental-economics-and-management/https-www-sciencedirect-com-science-article-pii-s0095069625001305.html`
- `samples/sciencedirect/journal-of-corporate-finance/https-www-sciencedirect-com-science-article-pii-s0929119925001841.html`
- `samples/sciencedirect/journal-of-banking-finance/https-www-sciencedirect-com-science-article-pii-s037842662500202x.html`
- `samples/sciencedirect/research-policy/https-www-sciencedirect-com-science-article-pii-s0048733325001763.html`
- `samples/sciencedirect/energy-economics/https-www-sciencedirect-com-science-article-pii-s0140988325008564.html`
- `samples/sciencedirect/energy-policy/https-www-sciencedirect-com-science-article-pii-s0301421525004689.html`
- `samples/sciencedirect/journal-of-comparative-economics/https-www-sciencedirect-com-science-article-pii-s0147596725000873.html`
- `samples/sciencedirect/journal-of-accounting-&-economics/https-www-sciencedirect-com-science-article-pii-s0165410125001811.html`
- `samples/sciencedirect/journal-of-empirical-finance/https-www-sciencedirect-com-science-article-pii-s0927539825001436.html`
- `samples/sciencedirect/explorations-in-economic-history/https-www-sciencedirect-com-science-article-pii-s0014498325001093.html`

这些文件目前只包含静态 fallback（需要 JS Hydration 才会填充正文）。采样器会等待 `script#__NEXT_DATA__`（Next.js JSON payload）出现，并将 JSON 序列化到 `<pre id="browser-snapshot-data">`，parser 可直接读取这段文本而无需依赖 DOM。

## 访问要求
- ScienceDirect 仍走 Cloudflare，需携带 `cf_clearance`、`TDMSessionID` 等 Cookie。
- 需要设置 `Accept: text/html`、`Accept-Language` 以及 `Sec-CH-UA-*` 头与浏览器一致。
- Playwright 建议通过 `SCIENCEDIRECT_BROWSER_CHANNEL=chrome` 或 `SCIENCEDIRECT_BROWSER_EXECUTABLE=/Applications/Google Chrome.app/...` 强制使用系统 Chrome，并指向手工预热的 `SCIENCEDIRECT_USER_DATA_DIR`。
- Playwright 中应 `await page.wait_for_selector("script#__NEXT_DATA__")`，然后 `json.loads` 其 `text_content()`，不必依赖渲染后的 DOM。

## 字段映射（须在 JSON 中提取）

| Field | Selector / Strategy | Notes |
| --- | --- | --- |
| Title | `<h1 data-qa="article-title">` → join `stripped_strings`; fallback `meta[name="citation_title"]`. | fallback DOM 的标题位于 Article preview 顶部，同时仍写入 `citation_title`。 |
| Authors | `section[data-qa="author-group"] [data-qa="author-name"]`; fallback `meta[name="citation_author"]`. | 每个 author 容器内的 `[data-qa="author-affiliation"]` 包含机构文字；meta 可作兜底但不含上标映射。 |
| Affiliations | `data-qa="author-affiliation"` / `data-qa="author-affiliations"` | 直接读取 `stripped_strings` 并去除上标。 |
| DOI | `meta[name="citation_doi"]` 或 DOM `a[href*="doi.org"]`. | fallback DOM 通常没有 `window.__NEXT_DATA__`，但 `<meta>` 仍给出标准 DOI。 |
| PII | `meta[name="citation_pii"]`、DOM 中 `data-pii`、或 URL `/pii/<ID>`. | 没有 JSON 时依赖 `<meta>` 或文件名解析；必要时构造 `https://www.sciencedirect.com/.../pii/<ID>`. |
| Publication date | `meta[name="citation_publication_date"]`；兜底 `[data-qa="publication-date"]`. | DOM 常见文案 “Available online ...” 需用 `dateutil`/正则解析。 |
| Abstract | `section#abstracts [data-qa="abstract-text"]` 拼接段落；兜底 `meta[name="citation_abstract"]`. | fallback 页面仍会渲染首段摘要，只是无交互。 |
| Keywords/JEL | `section[data-qa="keywords"] [data-qa="keyword"]`; 其次 `meta[name="citation_keywords"]`（`;`/`,` 分隔）. | 某些文章没有 keywords，此时 parser 需记录缺失原因。 |
| Highlights | `section[data-qa="highlights"] [data-qa="highlight-item"]`. | 无 JSON 时 `Highlights` 仍在 DOM，可与 keywords 一起用作特征。 |
| PDF link | `<a data-qa="download-pdf">` `href`; 兜底 `meta[name="citation_pdf_url"]`; 再次 fallback `https://www.sciencedirect.com/science/article/pii/<PII>/pdf?isDTMRedir=true`. | fallback DOM 仍渲染下载按钮，只是有时被 Cloudflare 拦截。 |

## 额外注意
- `window.__NUXT__` 不存在，当前站点使用 Next.js/React。必须解析 `script#__NEXT_DATA__`（保存在 `<pre id="browser-snapshot-data">`）。
- 若 `samples/` 仍是 fallback，可使用 `uv run econ-atlas samples import sciencedirect <slug> <file>` 导入手工保存的 HTML/JSON，再运行 parser 回归。
- 自动化采样前请运行 `uv run econ-atlas samples scd-session warmup`，并把输出的 profile 路径填入 `.env` 的 `SCIENCEDIRECT_USER_DATA_DIR`。
- CLI 会检查 HTML 是否包含 `<pre id="browser-snapshot-data">`/`window.__NEXT_DATA__`，缺失时会失败并提示查看 `samples/_debug_sciencedirect/<slug>.(png|html|zip)` 调试。
- ScienceDirect 允许通过 Elsevier TDM 接口抓结构化 JSON（需注册 key），可评估是否直接替代 DOM 抓取。***
- 运行 `uv run econ-atlas samples parse sciencedirect --input samples/sciencedirect` 可批量解析 fallback HTML，输出字段覆盖率与缺失原因；命令会在任一必填字段缺失时退出非零，便于早期发现 DOM 变更。
- 主 `econ-atlas crawl` 在检测到 `ELSEVIER_API_KEY` 时会默认走 Elsevier API；只有在 API 缺失或报错时才退回本页描述的 DOM fallback。无论 API 还是 fallback 失败，都只是记录警告，不会阻塞其他期刊。
