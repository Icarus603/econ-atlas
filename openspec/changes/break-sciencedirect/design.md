## Overview
ScienceDirect 拦截 headless 请求的主要策略：检测 `navigator.webdriver`、Referer/UA 不匹配、缺少持久化 Cookie，以及要求执行 bundler JS 才会注入 `window.__NEXT_DATA__`。目前我们已将 URL 重写为 `/pii/`，但仍难以获得真实 DOM。

## Proposed Architecture
1. **增强 Playwright context**
   - 启动 Chromium 时允许指定 `user_data_dir`（来自 `.env`），复用人工浏览器拦到的 Cloudflare session。
   - 在 `context.add_init_script` 中写入 anti-bot JS：伪装 `navigator.webdriver=false`、伪造插件/语言/时区、mock `chrome.runtime`。
   - 加载额外 headers/cookies（继续沿用 `.env` 中的 JSON），确保与浏览器截取的一致。

2. **JSON 抽取策略**
   - 等待 `script#__NEXT_DATA__` 或 `window.__NUXT__`；若出现，执行 `JSON.stringify(window.__NEXT_DATA__)` 并写入 `<pre id="browser-snapshot-data">`，与 HTML 同步保存。
   - 若 30s 仍未出现，记录日志 + 截图 + network HAR（Playwright tracing），方便分析。
   - Parser 之后可直接读取 `<pre id="browser-snapshot-data">` 中的 JSON，跳过 DOM。

3. **手工导入/调试命令**
   - 提供 `samples import sciencedirect --from <path>` command，接受 `.html` / `.json`（例如用户在 Chrome 里 `Save Page As`），并写入 `samples/sciencedirect/...`。
   - 在自动模式失败时，提示用户使用 `--sdir-debug` Export（包括 screenshot + logs），便于内部复现。

4. **Configuration surface**
   - `.env` 中扩展：`SCIENCEDIRECT_USER_DATA_DIR`、`SCIENCEDIRECT_DEBUG=1`、`SCIENCEDIRECT_FINGERPRINT_SCRIPT` 等。
   - README 增加“如何导出 cookie/headers/har”、“如何启用 debug trace”。

## Risks
- 持久化 user-data-dir 需要谨慎保护 Cookie（不能提交仓库）。
- Cloudflare 可能随时升级策略，需要灵活配置脚本。
- JSON 导出要避免含有 PI/Account 信息，需在文档里声明用途和敏感性。
