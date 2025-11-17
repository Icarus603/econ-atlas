## Why
ScienceDirect 仍然把 Playwright 提供的 Chromium 视为自动化浏览器，即便复用手工预热的 profile 也会持续跳转 Cloudflare 验证，导致 `window.__NEXT_DATA__` 无法捕获。为了在采样阶段继续使用真实 Chrome 指纹，需要让浏览器采样器可以指定 Chrome stable channel / 可执行路径，而不是只能使用 Playwright 自带的 Chromium。

## What Changes
- 为受保护的采样源新增可配置的 `*_BROWSER_CHANNEL` / `*_BROWSER_EXECUTABLE` 环境变量，并由 `samples collect` 在调用 Playwright 时带上。
- Playwright fetcher 支持 `channel` / `executable_path` 选项，并在持久化上下文及普通上下文均生效。
- 更新 README / README_CN / `.env.example` / parser profile 文档，解释如何指向系统 Chrome 来提升可信度。
- 扩充采样器单元测试，覆盖 env 解析与参数传递，确保回归。

## Impact
- 科学出版社尤其是 ScienceDirect 可以直接复用系统 Chrome（含 TLS 指纹、证书存储），大幅降低被 Cloudflare 阻挡的几率。
- 其余受保护站点若需要同策略也可沿用，默认行为保持不变。
