## TODO
- [x] 1. 扩展 Playwright fetcher：新增 `browser_channel` / `executable_path` 参数，并让 `launch` 与 `launch_persistent_context` 使用这些可选项（含互斥校验）。
- [x] 2. 在 `sample_collector` 中读取 `*_BROWSER_CHANNEL`、`*_BROWSER_EXECUTABLE` 环境变量（含错误提示），并把值传递给 fetcher；为 ScienceDirect 仍保留 profile 检查。
- [x] 3. 更新/新增测试覆盖 env 解析、fetcher 参数，以及 `.env.example`/README/README_CN/parser profile 文档以指导设置真实 Chrome。
