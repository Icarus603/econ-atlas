## 1. Warmup CLI
- [x] 1.1 新增 `samples scd-session warmup` 子命令：接受 `--profile-dir`, `--pii`, `--export-local-storage` 等参数，调用 Playwright headed persistent context，运行完后输出提示。
- [x] 1.2 命令执行时验证 profile 目录存在/可写，并提供交互提示（如何在页面里手动完成验证、如何退出）。

## 2. 采样强化
- [x] 2.1 在 ScienceDirect 采样前强制检查 `SCIENCEDIRECT_USER_DATA_DIR` 是否配置，否则直接 fail 并提示执行 warmup。
- [x] 2.2 抓取完成后检查 DOM 是否包含 `window.__NEXT_DATA__` 或 `<pre id="browser-snapshot-data">`，缺失时将该条标记为失败并附带调试建议。
- [x] 2.3 当 `--sdir-debug` 生效时，同时写入 trace/screenshot/DOM 片段路径，便于诊断。

## 3. 资产导入/导出
- [x] 3.1 提供 helper 将当前浏览器 localStorage dump 成 JSON（warmup 命令中或独立 flag），并更新 `.env` 片段说明。
- [x] 3.2 更新 `.gitignore`/README/README_CN 以及 `docs/parser_profiles/sciencedirect.md`，写明 warmup 步骤、profile 目录约定、安全注意事项。

## 4. 验证
- [x] 4.1 为新命令与 JSON 检查添加单元测试（例如 mock 出无 JSON 的 DOM，确保命令抛错），并更新现有 sample collector 测试。
- [x] 4.2 运行 `uv run ruff check . --fix`, `uv run mypy .`, `uv run pytest -q`。
