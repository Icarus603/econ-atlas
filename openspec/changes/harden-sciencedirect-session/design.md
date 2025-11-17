## Overview
当前 `SampleCollector` 虽然暴露了 user-data-dir / localStorage / init-script 等钩子，但它只在 env 已经配置的情况下启用，而且 headless 流程没有检查 `__NEXT_DATA__` 是否成功写入。我们需要一个“会话生命周期”：

1. **Warmup** – 启动一个持久化 Chromium，使用用户指定（或默认）的 profile 路径，在 headed 模式里让操作者完成验证。此时 Playwright 必须 `launch_persistent_context(user_data_dir=...)`，这样 Cloudflare 生成的 token/LocalStorage 被保存下来。
2. **Persist** – warmup 结束后提供命令将 profile 路径写入 `.env` 或输出 shell 片段，方便后续 `samples collect` 自动加载；同时支持将新 localStorage 导出为 JSON，写入 `SCIENCEDIRECT_BROWSER_LOCAL_STORAGE`。
3. **Verify** – 采样时如果 `__NEXT_DATA__` 没出现，就立刻 fail 并提示用户重新 warmup，必要时导出调试 trace。

## Proposed Architecture
1. **新 CLI 子命令**
   - `samples scd-session warmup [--profile-dir PATH] [--open-dashboard]`: 创建/确认 profile 目录，再以 headed 模式打开一个页面（默认 `https://www.sciencedirect.com` 或指定 `pii` URL）。
   - 命令退出时，打印 profile 目录、最近写入的 cookie/localStorage key，并提醒更新 `.env`。
   - 允许 `--export-local-storage <file>` 将当前 localStorage dump 为 JSON，便于 `.env` 使用。
2. **SampleCollector 验证**
   - 浏览器模式完成后，在 DOM 中查找 `window.__NEXT_DATA__`。如果找不到，就抛出自定义异常，将该条列入 `report.errors`，同时把 `trace.zip`、截图路径打印出来。
   - 对 ScienceDirect 强制要求 `user_data_dir` 存在，否则在运行前就 fail 并提示执行 warmup 命令。
3. **Session 资产托管**
   - 在项目根 `.gitignore` 保持/新增忽略路径（例如 `.cache/econ-atlas/scd-profile`）。
   - 通过 helper 函数复制整份 profile（或 symlink）以供 Playwright 调用；这一步也可以沿用用户提供的路径。

## Alternatives Considered
- **直接 HTTP 抓 JSON**：需要额外的 API key 或逆向 Cloudflare token，时间成本高且易失效，因此暂不作为本次迭代目标。
- **Playwright Stealth 插件**：虽然可以隐藏 webdriver，但仍需持久化会话；stealth 只能缓解指纹问题，无法替代真实 profile，因此仍以 profile + manual warmup 为主线。

## Open Questions
- Warmup 命令是否需要自动把 profile 路径写入 `.env`？（可以追加 `--write-env` 开关，默认只打印）
- 是否需要对 profile 目录进行压缩备份，还是直接引用用户提供的路径即可？（初版可以只引用路径，留给用户自行管理磁盘）
