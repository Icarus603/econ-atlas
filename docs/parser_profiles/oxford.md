# Oxford University Press（academic.oup.com）

## 样本与现状
- `samples/oxford/quarterly-journal-of-economics/http-doi-org-10-1093-qje-qjaf039.html`
- `samples/oxford/review-of-economic-studies/http-doi-org-10-1093-restud-rdaf060.html`
- `samples/oxford/economic-journal/http-doi-org-10-1093-ej-ueaf065.html`
- `samples/oxford/review-of-financial-studies/http-doi-org-10-1093-rfs-hhaf065.html`

这些 HTML 同样还是 Cloudflare 验证页。需要在浏览器中完成验证后抓取 `https://academic.oup.com/<journal>/advance-article/doi/<doi>` 页面。

## 访问要求
- RSS Feed + DOI 页面都走 Cloudflare；需要捕获 `cf_clearance`、`__cf_bm` 等 Cookie 并在 Playwright 里注入。
- 登录一般只在订阅内容时需要，大多数文章只要人机验证即可。
- 建议在 Playwright 里等待 `document.querySelector("article.article")` 出现后再导出 `page.content()`.

## 字段映射（预期 DOM）

| Field | Selector / Strategy | Notes |
| --- | --- | --- |
| Title | `meta[name="dc.Title"]` / `h1.wi-article-title` | OUP 使用 HighWire/Atypon 栈，标题在 `article.article` 内也有。 |
| Authors | `meta[name="citation_author"]` + `meta[name="citation_author_institution"]` | DOM 中 `.wi-article-author-list` 也列作者，含 `data-test="author-name"`. |
| Affiliations | `.al-authors-list .institution` 或 `meta[name="citation_author_institution"]` | 同一个作者可能有多条 affiliation，需要拆分 `;`. |
| DOI | `meta[name="citation_doi"]` 或 `.article-metadata .doi a` | `data-doi` 属性也可直接读取。 |
| Publication date | `meta[name="citation_publication_date"]`（`YYYY/MM/DD`） | 页面侧栏的 `Published:` 文本可作为校验。 |
| Abstract | `section.article-section.article-abstract` | 也有 `meta[name="citation_abstract"]`，DOM 还包含 `<div class="abstract">`。 |
| Keywords/JEL | `section.article-metadata .kwd-group li` | JEL（如有）会放在 `section#JEL` 或文章末尾表格，需要额外 selector。 |
| PDF link | `meta[name="citation_pdf_url"]` + `.al-link.pdf` | 无需拼 query；直接下载地址包含 `pdf`. |

## 额外注意
- 如果 Cloudflare 仍返回 403，需要使用 RSS 页面 `Copy as cURL` 获取完整 header（包括 `Accept-Language`、`Sec-CH-UA-*`）。
- Playwright 输出 HTML 后需检查 `<title>` 是否为 “Just a moment…”。如是，视为失败重新采样。***
