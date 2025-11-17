## 1. DOM 勘测与样本准备
- [x] 1.1 梳理 fallback `Article preview` DOM 与 meta 标签，确认标题、作者列表、affiliation、DOI、摘要、PDF/关键字等 selector，并记入 parser profile。
- [x] 1.2 从 `samples/sciencedirect/**/*` 里挑选至少 2 份代表性 HTML，脱敏后放入测试夹具（或以 snapshot 形式存档），确保可在 CI 中复现。

## 2. Parser 实现
- [x] 2.1 在 `src/econ_atlas` 新增 ScienceDirect fallback parser（含 dataclass/DTO），实现字段抽取、PII/DOI 推断以及缺失字段标记。
- [x] 2.2 编写单元测试覆盖常见变体（多作者、多段摘要、无 PDF 等），对照夹具验证输出。
- [x] 2.3 暴露解析入口（函数或 Typer 命令）供后续 CLI/脚本调用，并保证 mypy/ruff 通过。

## 3. 集成与文档
- [x] 3.1 提供 CLI 或脚本入口（如 `econ-atlas samples parse ...`）批量跑 parser 并导出 JSON，供手工/CI 验证。
- [x] 3.2 更新 README 与 `docs/parser_profiles/sciencedirect.md`，说明 fallback 解析流程、局限与验证方式。
- [x] 3.3 运行 `uv run ruff check . --fix`, `uv run mypy .`, `uv run pytest -q`，确认解析模块与测试全部通过。
