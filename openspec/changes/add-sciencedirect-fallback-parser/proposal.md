## Why
- ScienceDirect 目前长期只返回 fallback `abs` HTML，`window.__NEXT_DATA__` 始终缺失，先前的 parser 计划完全依赖 JSON，导致整个来源无法产出结构化字段。
- RSS 只提供标题/摘要，缺少 DOI、作者、JEL、PDF 等资讯；没有 fallback DOM 解析，`data/*.json` 就永远停留在半成品，无法支撑下游分析或对比其它出版社。
- 虽已能收集大量 fallback HTML 样本，但仓库缺乏一个“把静态 DOM 解析为统一 Article schema”的流程，既无法验证字段覆盖，也无法在 CLI 中复用，ScienceDirect 成为唯一空白来源。

## What Changes
1. **DOM 勘测与 schema 取舍**：系统化梳理 fallback `Article preview` DOM，记录标题、作者、摘要、PDF 链接等 selector 以及缺失字段的兜底策略（如从 `meta` 标签/URL 推断 DOI、利用 `Highlights` 填补关键词）。
2. **实现 parser 组件**：在 `src/econ_atlas` 下新增 ScienceDirect fallback 解析模块，输入 HTML/PII，输出结构化记录（含字段缺失标记）。解析器需容错（多语言、列表/富文本、作者多 affiliation）并内建检测逻辑以便 CLI/测试调用。
3. **集成与回归验证**：提供 CLI/脚本（例如 `econ-atlas samples parse sciencedirect <html>` 或 pytest fixture）批量跑 parser，对 `samples/sciencedirect/**/*` 生成 JSON，编写单元+回归测试确保字段映射稳定，同时在 README / parser profile 更新“fallback 解析”步骤。

## Impact
- 需要维护一套 DOM selector/正则，后续若 ScienceDirect 再改版必须同步调整，不过相比等待 `__NEXT_DATA__` 恢复风险更低。
- parser 输出的字段可能仍不完整（JEL/keywords 缺失），必须设计缺失报告机制，防止错误地把空值当作“字段不存在”。
- CLI/测试会多一个解析步骤，可能增加运行时间；但能立即让 ScienceDirect 产生结构化记录，为后续替换为 TDM/API 提供对比基准。
