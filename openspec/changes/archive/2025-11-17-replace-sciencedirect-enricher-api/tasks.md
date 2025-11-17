## 1. API 集成
- [x] 1.1 调研 Elsevier API（Article Retrieval / Search）的请求参数、速率、字段，确定最适合替换 DOM parser 的端点。
- [x] 1.2 在配置层支持 `ELSEVIER_API_KEY`（以及所需的 Institutional Token/Secret，如必须），提供验证与错误信息。
- [x] 1.3 实现 ScienceDirect API 客户端（含重试、速率限制、错误分类），并在缺少 key 时优雅地禁用。

## 2. Enricher 替换
- [x] 2.1 用 API 客户端替换 `ScienceDirectFallbackEnricher` 的 Playwright 路径，直接把 JSON 映射到 ArticleRecord；保留 DOM parser 作为后备。
- [x] 2.2 更新 Runner，确保翻译计数/错误统计在 API 模式下准确，且在 API 不可用时继续执行。
- [x] 2.3 增加全面的单元/集成测试：API 成功、API 失败回退、无 key 情况、速率/错误日志等。

## 3. 文档与示例
- [x] 3.1 更新 README、docs/parser_profiles/sciencedirect.md，说明 API Key 获取方式、配置步骤、fallback 行为。
- [x] 3.2 更新 `.env.example`，添加 `ELSEVIER_API_KEY` 以及相关说明；必要时在 CLI 输出中提示缺失 key。
- [x] 3.3 运行 `uv run ruff check . --fix`, `uv run mypy .`, `uv run pytest -q`，确保所有路径通过。
