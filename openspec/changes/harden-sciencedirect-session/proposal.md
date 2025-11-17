## Why
- 即便提供最新 cookie/UA，Playwright 仍经常被 ScienceDirect 识别为自动化会话，页面一直停留在 Cloudflare fallback，导致 `samples/sciencedirect/*.html` 没有 `__NEXT_DATA__` JSON，也无法推进 parser。
- 现有 CLI 虽支持 env 配置 user-data-dir、localStorage 等参数，但没有引导用户准备真实浏览器 profile，也没有验证 JSON 是否写入，导致“看似成功但其实抓到空壳”。
- 缺乏一个“手动通过挑战 → 自动复用会话”的闭环：我们需要一键拉起可交互 Chromium，让用户亲自通过验证，同时持久化 profile，供后续 headless 采样沿用。

## What
1. **ScienceDirect 会话引导命令**：新增 `uv run econ-atlas samples scd-session warmup`（名称待定）之类的 CLI，使用 `launch_persistent_context` + `headless=false` 打开带指定 profile 的 Chromium，让操作者在真实浏览器里完成登录/验证码/Cloudflare 检查。命令完成后要确认 profile 路径写入 `.env` 并提示如何再次运行采样。
2. **强制校验 JSON**：`samples collect` 在保存 ScienceDirect HTML 时若找不到 `<pre id="browser-snapshot-data">` 或 `__NEXT_DATA__`，必须将该条记为失败并输出调试建议（是否缺 profile、是否需要 warmup、headless/trace 路径等）。
3. **Session 资产托管**：提供 helper（可以是 CLI 子命令或脚本）把当前 Chromium profile / localStorage / cookies 复制到仓库的忽略目录（例如 `.cache/econ-atlas/scd-profile`），并写入 `.env` 中的 `SCIENCEDIRECT_USER_DATA_DIR`。同时允许从 JSON 文件导入 localStorage（`SCIENCEDIRECT_BROWSER_LOCAL_STORAGE`）并持久化到 profile。
4. **文档更新**：README / README_CN 以及 `docs/parser_profiles/sciencedirect.md` 要增加“如何 warmup 会话、如何确认 JSON 已写入、如何排查 fallback”章节。

## Impact
- 需要 Playwright 在运行中能切换 persistent context、headed 模式、以及额外 CLI 子命令，命令执行时间会延长，但这是获取可靠 JSON 的必要成本。
- 开发者需要在本地存储浏览器 profile，必须明确提醒不要把真实 cookie 提交到 git（依旧在 `.gitignore`），文档需强调安全性。
- `samples collect` 失败信息更多，会促使团队尽快完成 warmup，而不是误判脚本已经成功抓到数据。
