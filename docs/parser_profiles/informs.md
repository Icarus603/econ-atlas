# INFORMS（pubsonline.informs.org）

## 样本现状
- `samples/informs/management-science/` 目录为空。RSS `https://pubsonline.informs.org/action/showFeed?type=etoc&feed=rss&jc=mnsc` 一直 403。

## 访问要求
- 需要从浏览器成功访问 RSS，并复制完整 cURL（含 `cf_clearance`、`JSESSIONID`、`MAID` 等）。
- DOI 页面也走 Cloudflare，建议预先访问一次 `https://pubsonline.informs.org/doi/abs/<doi>` 并复用 Cookie。

## 字段映射（Atypon/HighWire 模板）

| Field | Selector / Strategy | Notes |
| --- | --- | --- |
| Title | `meta[name="dc.Title"]` / `h1.wi-article-title` | 和 Oxford/Chicago 相同。 |
| Authors | `meta[name="citation_author"]` + `.al-authors-list` | 需要解析作者脚注 `<sup data-ref-type="aff">`. |
| Affiliations | `meta[name="citation_author_institution"]` / `.affiliation-list li` | DOM 里 `span.aff :` 结构固定。 |
| DOI | `meta[name="citation_doi"]` | 也存在 `a[title="DOI"]`. |
| Publication date | `meta[name="citation_publication_date"]` | 文章信息块 `.articleMetaDate`. |
| Abstract | `section.article-section.article-abstract` | “Read More” 需在采样时点击 `button.more`. |
| Keywords/JEL | `.kwd-group li` | JEL seldom provided；`Keywords`  usually available. |
| PDF link | `meta[name="citation_pdf_url"]` / `.al-link.pdf` | PDF 请求也在 Cloudflare 保护下，注意复用 Cookie。 |

## TODO
- 解决 RSS 403，确认 `samples/informs/.../*.html` 存在后再验证 selector。
- 记录管理科学以外的 INFORMS 期刊 slug（如 `marketing-science`）以便批量测试。***
