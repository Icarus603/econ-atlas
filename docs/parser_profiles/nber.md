# NBER（www.nber.org）

## 样本
- `samples/nber/nber/i768l2-sitesearch-entity-node-1172283-en.html`
- `samples/nber/nber/i768l2-sitesearch-entity-node-1185739-en.html` 等若干

HTML 直接包含 `<meta name="citation_*">`，解析难度最低。

## 访问要求
- feed `https://www.nber.org/api/v1/working_page_listing/...` 返回 JSON，字段 `item["detail_view"]` 只含相对路径（例如 `/papers/w34381`），采样脚本必须拼 `https://www.nber.org`.
- 不需要 Cookie；`User-Agent` 设为浏览器字符串即可。

## 字段映射

| Field | Selector / Strategy | Notes |
| --- | --- | --- |
| Title | `meta[name="citation_title"]` 或 `<h1 class="page-title">` | 需要 HTML 解码 `&rsquo;` 等。 |
| Authors | 多个 `meta[name="citation_author"]` / DOM `.author-list li` | 页面同时列出 `meta[name="citation_author_email"]`。 |
| Affiliations | `meta[name="citation_author_institution"]` 缺失；需要从正文 `div#system-main` 中 `p` 文本提取（通常写在脚注）。 | 若解析不到，返回 `None`. |
| DOI | `meta[name="citation_doi"]`（形如 `10.3386/w34381`） | 也可组合 `https://doi.org/` + 工作论文号。 |
| Publication date | `meta[name="citation_publication_date"]` => `YYYY/MM/DD` | DOM `span.work-paper-date` 供校验。 |
| Abstract | `meta[name="description"]` 是短摘要；完整版在 `div.node-abstract`. | Parser 应优先 DOM 版以保留 `<p>`. |
| Keywords/JEL | 页面未公开关键词/JEL，字段留空；若需 JEL，可从 PDF 封面 OCR。 | 文档中记录 “Not provided”. |
| PDF link | `meta[name="citation_pdf_url"]` | 直接下载，不需 cookie。 |

## 额外注意
- Feed 返回 `i768l2-sitesearch-entity:node/<id>:en` 作为 `entry_id`，需要映射到 slug 以避免重复文件名。
- 在 `SampleCollector` 中应确保保存的 HTML 里 `Request URL` 已补足 `https://www.nber.org`.***
