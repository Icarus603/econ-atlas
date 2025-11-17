## 1. 样本盘点
- [x] 1.1 编写脚本或 CLI 子命令，扫描 `samples/<source_type>/<slug>/*.html`，输出每个 `source_type` 的样本数量、最近抓取时间，生成机器可读清单（JSON/CSV）。
- [x] 1.2 为 Chicago/INFORMS/NBER 等缺样本来源补充备注（例如需要 RSS Cookie 或备用 feed），记录在清单里。

## 2. DOM 逆向文档
- [x] 2.1 依据样本，为 Wiley、Oxford、ScienceDirect、Cambridge、NBER（以及现有 `samples/` 中的其它 `source_type`）分别创建 `docs/parser_profiles/<source_type>.md`，列出字段 selector、步骤和依赖。
- [x] 2.2 在文档中加上使用到的样本文件路径、是否需要登录、Cookie/Headers，以及 parser 需要处理的交互（展开摘要、加载更多作者等）。

## 3. 覆盖率校验
- [x] 3.1 新增一个校验脚本（可集成到 `uv run pytest` 或独立命令），确保 `docs/parser_profiles/` 至少覆盖当前 `samples/` 中的每个 `source_type`，缺失时给出提示。
- [x] 3.2 为校验逻辑写单元测试，模拟有/无文档、字段缺失等情况，保证 CI 可检测文档遗漏。

## 4. 操作指南
- [x] 4.1 更新 `README_CN.md`（必要时 README.md）介绍 DOM 逆向流程：如何打开样本、如何记录 selector/字段、如何更新覆盖清单，以及 Playwright 采样和 DOM 文档之间的关系。
