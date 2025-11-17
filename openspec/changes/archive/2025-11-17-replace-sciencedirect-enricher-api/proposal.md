## Why
- ScienceDirect 当前依赖 Playwright + fallback DOM 解析，必须人工维持浏览器 profile/cookie，不能满足“无人值守”需求。
- Elsevier TDM API 已申请成功，可直接返回结构化 JSON（标题、作者、DOI、摘要等），更稳定、速率可控。
- 需要用 API 替换现有的 `ScienceDirectFallbackEnricher`，并保留缺省回退（无 API key 或调用失败时不影响 RSS 基础流程）。

## What Changes
1. **API 配置与凭证**：在配置层支持 `ELSEVIER_API_KEY`（以及可选的机构 ID/密钥），Crawler 自动检测 key，走 API 逻辑，不再触发 Playwright。
2. **新的 ScienceDirect API Enricher**：实现基于 Elsevier API 的 fetch → 字段映射 → 翻译逻辑，涵盖速率限制、重试、错误处理。保留旧 DOM parser 作为兜底（仅当 API 返回 404/403 或未配置 key 时使用）。
3. **CLI/文档更新**：README 与 parser profile 改为说明 API 模式是默认路径，只有缺少 key 才需 fallback；`.env.example` 提供 `ELSEVIER_API_KEY` 模板。
4. **测试与监控**：新增 API 调用的单元测试（使用假客户端），并为 Runner 增加确保在缺失 key 时仍能运行的覆盖。

## Impact
- 运行时将不再依赖 Playwright 处理 ScienceDirect（除非 API 不可用），显著降本且真正实现无人值守。
- 需要管理 API key、速率限制与错误重试，但这比维护浏览器会话可控得多。
- 新增依赖（httpx/SDK）与配置项，需在 README/.env.example 清晰说明。
