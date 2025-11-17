## Why
- 已经用 Playwright 抓到了大量 Wiley/Oxford/ScienceDirect 等站点的文章 HTML，但仓库里没有任何 DOM 结构记录，解析器无法根据这些样本快速落地。
- 仍有 Chicago、INFORMS 等 RSS 无法访问，需要先把 RSS/文章页面的 DOM 也分析出来，明确需要哪些 cookie/headers 才能提取。
- 对每个 `source_type` 的 DOM 特征缺乏文档，导致 parser 开发只能反复「打开 HTML 慢慢看」，效率低且不可复现。

## What Changes
1. 建一个 `docs/parser_profiles/` 目录，按照 `source_type` 维护 Markdown 记录：列出字段（标题、作者、机构、DOI、发布日期、摘要/关键词、PDF 链接、JEL 等）所对应的 CSS/XPath、需要点击/展开的交互以及依赖的 cookie/headers。
2. 写一个 inventory/校验脚本，从 `samples/<source_type>/.../*.html` 枚举所有样本，并生成覆盖表（哪些字段有样本、有解析方案、还缺样本）以便后续 parser 实现按表推进。
3. 在 `README_CN.md` 加一节「如何逆向 DOM」：包括推荐的浏览器工具、如何记录 selector、以及如何在样本更新后同步文档。
4. 更新 `source-profiling` 规格，新增“DOM 逆向文档”要求，并给出任务列表（整理样本、完成文档、加校验脚本、补充 README）。

## Impact
- 提供结构化的 DOM 说明书，parser 实现能直接照表写代码，减少返工。
- 增加一批文档/脚本需要维护，但量化了覆盖率，方便追踪缺失站点。
- 也让新同学能快速了解各出版社在登录、Cookie、防护上的差异，降低知识蒸发风险。
