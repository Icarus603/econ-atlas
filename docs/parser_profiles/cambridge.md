# Cambridge Core（cambridge.org/core）

## 样本
- `samples/cambridge/journal-of-economic-history/https-dx-doi-org-10-1017-s0022050725100843-rft-dat-source-3ddrss.html`
- `samples/cambridge/journal-of-financial-and-quantitative-analysis/https-dx-doi-org-10-1017-s0022109024000930-rft-dat-source-3ddrss.html`

HTML 内已经包含完整内容与 `window.__NUXT__` 的 JSON，可直接逆向。

## 访问要求
- 只要完成 OneTrust cookie banner，Cambridge Core 即返回完整静态 HTML；无需额外 Cookie。
- 为避免 `window.location.reload` (OneTrust) 影响，Playwright 在 `page.route` 拦截 `OtAutoBlock.js` 即可。

## 字段映射

| Field | Selector / Strategy | Notes |
| --- | --- | --- |
| Title | `meta[name="citation_title"]` 或 `script` 中 `window.__NUXT__.data[0].article.metadata.title` | DOM 里 `h1[data-qa="article-title"]`. |
| Authors | 多个 `meta[name="citation_author"]` + `window.__NUXT__.data[0].article.metadata.authorsGroup.authors.contributors` | JSON 中每位作者含 `affiliations[text]` 与 `email`。 |
| Affiliations | `meta[name="citation_author_institution"]` 顺序与作者匹配；也可从 JSON 的 `affiliations` 拿全文描述。 | DOM `.article-header__author-affiliations li`. |
| DOI | `meta[name="citation_doi"]` 或 JSON `article.metadata.doi.value` | 链接在 `.article__doi a`. |
| Publication date | `meta[name="citation_publication_date"]`（YYYY/MM/DD） | JSON `article.metadata.publishedDate` 为 “18 July 2025”，需标准化。 |
| Abstract | `meta[name="citation_abstract"]` 与 DOM `section[data-qa="abstract"]` | DOM 版本保留 `<p>`、`<em>`；可作为 translation 输入。 |
| Keywords/JEL | JSON `article.metadata.keywords`（列表 `[{text:\"...\"}]`）。DOM 目前没渲染关键词，因此需要直接读 JSON。 | JEL 若缺失可标记为空。 |
| PDF link | `meta[name="citation_pdf_url"]` | 也可从 `.article-actions__links a[href$=".pdf"]` 获取。 |

## 额外注意
- `window.__NUXT__` 序列化内容巨大，建议使用 `json.loads()` + `orjson` 解析以减轻内存。
- Keywords 目前为空数组，如果后续版本补齐，应更新文档并在 parser 中保留空值语义。***
