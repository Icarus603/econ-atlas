## Why
- ScienceDirect 仍是 list.csv 中期刊数量最多的来源，但当前 Playwright 采样即使注入 UA/Cookie 也只能拿到 fallback HTML，`script#__NEXT_DATA__` 始终不出现，阻塞了 parser 逆向。
- 缺乏稳定的反爬/会话策略（navigator.webdriver、持久化 cookie、重放浏览器行为等），导致每次运行都被 Cloudflare 标记，`samples/sciencedirect/*` 没有可解析 DOM/JSON。
- parser 需要结构化字段（标题、作者、摘要、PDF、JEL 等），若没有真实 DOM 或页面自带 JSON，就无法推进后续定制。

## What Changes
1. **浏览器指纹/会话增强**：为 Playwright context 提供 anti-bot 注入（覆盖 `navigator.webdriver`、`chrome.runtime`、插件枚举、timezone、language 等），并允许使用持久化 user-data-dir 或导入完整 Cookie+localStorage，以复用人工浏览器获取的 session。
2. **ScienceDirect 专用采样流程**：
   - 将请求统一到 `/science/article/pii/<ID>` 并在页面上执行 `window.__NEXT_DATA__`/`window.__NUXT__` 抓取，哪怕 DOM 不渲染也可保存 JSON。
   - 若 headless 依旧失败，回退为“半自动”模式：利用用户提供的 HAR/cURL，CLI 可根据 JSON/HTML 文件手工导入到 `samples/`，确保 parser 仍有样本。
3. **诊断与重试机制**：记录每次 ScienceDirect 采样的 HTTP 状态/挑战信息，提供 `--sdir-debug` 选项导出网络日志，方便调试 cookie 过期或 IP 被拦。
4. **文档/Spec 更新**：在 `source-profiling` 规格中新增对 ScienceDirect 的特定要求（必须保存 `__NEXT_DATA__` JSON、支持手工注入 cookie/headers/指纹），并补充 README/故障排查指南。

## Impact
- 采样 CLI 会依赖更多 Playwright 功能（persistent context、js 注入），运行时间和复杂度上升，但换来可用的 DOM/JSON 样本。
- 需要小心存储敏感 Cookie/Session（提供 `.env` 加密/警告），并确保导出日志不含凭证。
- 一旦 JSON 样本稳定，parser 可以直接开发 ScienceDirect 规则，解锁大量期刊数据。
