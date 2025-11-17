## 1. 反爬指纹研究与实现
- [x] 1.1 调研并记录 ScienceDirect / Cloudflare 常见检测点（`navigator.webdriver`、`permissions`、`chrome.runtime`、语言/时区等）。
- [x] 1.2 在 Playwright context 层实现 anti-bot 注入（JS snippet + timezone/language 覆盖），并提供 `.env` 钩子以开启/关闭。
- [x] 1.3 支持从用户提供的浏览器 profile（user-data-dir 或 HAR/cURL）导入 cookies/localStorage，验证可复用人工 session。

## 2. ScienceDirect 专用采样管线
- [x] 2.1 统一 DOI/PII URL 生成逻辑，确保请求落在 `/science/article/pii/<ID>`，必要时解析 RSS 中的 `pii`。
- [x] 2.2 执行 `window.__NEXT_DATA__`/`window.__NUXT__` 抓取，将 JSON 嵌入 HTML 或单独保存 `.json` 便于 parser 消费。
- [x] 2.3 针对超时/403 增加重试和 `--sdir-debug` 选项，输出网络日志/截图，帮助定位失败原因。
- [x] 2.4 提供“手工导入”命令：接受用户上传的 HTML/JSON（来自浏览器下载），写入 `samples/sciencedirect/...`，维持 parser 所需样本。

## 3. 测试与文档
- [x] 3.1 为新的 URL 重写、JSON 嵌入、anti-bot 注入编写单元测试（可用 fake browser fetcher 模拟）。
- [x] 3.2 更新 README/README_CN，描述 ScienceDirect 的配置方式（指纹注入、HAR 导入、调试日志）。
- [x] 3.3 在 `docs/parser_profiles/sciencedirect.md` 增加“JSON 抓取/解析”章节，说明 parser 如何消费 `__NEXT_DATA__`。
