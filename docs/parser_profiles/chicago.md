# University of Chicago Press（journals.uchicago.edu）

## 样本现状
- `samples/chicago/journal-of-political-economy/` 目录存在，但目前没有 HTML（RSS 被 Cloudflare 拦截）。
- RSS URL：`https://www.journals.uchicago.edu/action/showFeed?type=etoc&feed=rss&jc=jpe` —— 403，需要浏览器 Cookie。

## 访问要求
- 必须先在浏览器中访问 RSS 地址，通过人机验证后再 “Copy as cURL” 获取 Header + Cookie（尤其是 `cf_clearance`、`MAID`、`MACHINE_LAST_SEEN`）。
- 采样前建议把 RSS 响应保存一份，便于定位 `<item><link>`（Chicago 也使用 Atypon，引导至 `/doi/full/10.1086/...`）。

## 字段映射（需要真实 DOM 后验证）

| Field | Selector / Strategy | Notes |
| --- | --- | --- |
| Title | `meta[name="dc.Title"]` / `h1.wi-article-title` | Chicago Press 也是 Atypon，与 Oxford 结构一致。 |
| Authors | `meta[name="citation_author"]` + `.al-authors-list .author-name` | 需把脚注编号映射到 `meta[name="citation_author_institution"]`. |
| Affiliations | `meta[name="citation_author_institution"]` / `.author-info.affiliations` | DOM 中 `<li class="affiliation">` 包含完整地址。 |
| DOI | `meta[name="citation_doi"]` / `.articleinfo .doi a` | 以 `10.1086/<id>` 形式。 |
| Publication date | `meta[name="citation_publication_date"]` | 备用：`.articleInfo .pub-date`. |
| Abstract | `section.article-section.article-abstract` | 需展开 `div.more` 以取全文。 |
| Keywords/JEL | `.article-metadata .kwd-group` | 若没有关键字，可记 `None` 并在 parser 里跳过。 |
| PDF link | `meta[name="citation_pdf_url"]` / `.al-link.pdf` | 直接下载 PDF 时需同源 Cookie。 |

## TODO
- 获取可用 RSS Cookie 并验证 `samples collect --include-source chicago` 能真正拿到文章 HTML。
- 录入成功样本路径（至少 1 篇）。否则 parser 团队无法回放 DOM。***
