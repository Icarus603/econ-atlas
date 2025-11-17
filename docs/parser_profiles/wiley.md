# Wiley（onlinelibrary.wiley.com）

## 样本与现状
- `samples/wiley/international-economic-review/10-1111-iere-70036.html`
- `samples/wiley/journal-of-accounting-research/10-1111-1475-679x-70027.html`
- `samples/wiley/strategic-management-journal/10-1002-smj-70038.html`
- `samples/wiley/economic-history-review/10-1111-ehr-70068.html`

以上 HTML 仍是 Cloudflare “Just a moment…” 挑战页。需要在 Playwright 中等待挑战完成（通常需注入 `cf_clearance`、`MAID`、`MACHINE_LAST_SEEN` 等 Cookie，并保持和浏览器一致的 UA/Accept-Language）后重新采样，才能得到真实 DOM。

## 访问要求
- 需要可用的 Wiley 账号或机构 IP。匿名访问往往只要通过 Cloudflare 人机验证即可。
- RSS -> DOI 页面必须带上完整的 Cookie 组合（可在浏览器 DevTools 里对 RSS 访问使用 “Copy as cURL” 获取）。
- 建议在 `SampleCollector` 中针对 Wiley 显式 `await page.wait_for_url("https://onlinelibrary.wiley.com/doi/full/...")`，并在 `page.on("response")` 检测 `challenge-platform` 请求完成后再 `page.content()`.

## 字段映射（预期 DOM）

| Field | Selector / Strategy | Notes |
| --- | --- | --- |
| Title | `meta[name="dc.Title"]::attr(content)` 或 `.citation__title` 文本 | Wiley 所有文章页面都带 `dc.Title` & `citation_title`；标题中会包含实体引用需做 HTML 解码。 |
| Authors | 多个 `meta[name="citation_author"]` 或 `.article-section__contributors .author-name` | `citation_author_institution` 对应 affiliations，可按序 zip。 |
| Affiliations | `meta[name="citation_author_institution"]` 或 `.author-info__affiliation` | 若作者共享 affiliation，DOM 中会以脚注编号呈现，需要把编号映射回作者列表。 |
| DOI | `meta[name="citation_doi"]` 或 `.epub-section__doi a` | 部分页面还提供 `data-doi` 属性，方便直接提取。 |
| Publication date | `meta[name="citation_publication_date"]`（格式 `YYYY/MM/DD`） | 当只给出年月时，DOM 里 `span.publication-history__date--published-online` 会显示完整日期。 |
| Abstract | `meta[name="citation_abstract"]` 以及 `.article-section__abstract .article-section__content` | DOM 抽象区可能包含 `<p>` 分段；需要保留 `<sup>` 里的脚注引用。 |
| Keywords/JEL | `.article-section__keywords li`（数据写在 `data-keyword`） | 若页面无关键词，可以退回到 “Research Areas” chips。JEL 需从文章正文表格中识别。 |
| PDF link | `meta[name="citation_pdf_url"]` 或 `.epub-section__download a[href$=".pdf"]` | Wiley 同时提供 “Download PDF” 按钮和 `citation_pdf_url`，优先 meta。 |

## 额外注意
- 需要在 `.env` 中维护 `WILEY_COOKIES` & 可选 `WILEY_BROWSER_USERNAME/PASSWORD`，Playwright 初始化时写入。
- 采样结束后应人工 spot-check HTML，确认不再是 Cloudflare stub。否则 parser 无数据可解析。***
