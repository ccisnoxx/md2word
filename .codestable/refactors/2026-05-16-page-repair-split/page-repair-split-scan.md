---
doc_type: refactor-scan
refactor: 2026-05-16-page-repair-split
status: user-reviewed
scope: "`input_adapter_runtime.py` 中的页面修补链，以及主模块/共享测试 helper 对应的兼容导出"
summary: 发现 3 条优化点，结构 3 / 性能 0 / 可读性 0
---

# page-repair-split scan

## 总览

- 扫描范围：`input_adapter_runtime.py`、`page_repair_runtime.py`、`mineru_to_docx.py`、`tests/test_page_repair_characterization.py`、`tests/test_render_table_from_html_characterization.py`
- 发现 3 条优化点：结构 3 / 性能 0 / 可读性 0
- 按风险：低 1 / 中 2 / 高 0
- 建议先做：#1 #2 #3
- 建议慎做 / 后做：无
- 前置检查 7 条全过：✓

## 条目

### #1 把页面修补链从输入适配模块独立成新模块 ✓

- **位置**：`input_adapter_runtime.py:102-175`、`input_adapter_runtime.py:647-708`
- **分类**：结构
- **现状**：输入适配模块同时承载内容解析和页面修补两类职责
- **问题**：`input_adapter_runtime.py` 仍同时处理原始 JSON 适配和 middle/续表修补；同一文件跨两个稳定职责边界
- **建议**：新建 `page_repair_runtime.py`，承接页面修补、续表挂接和视觉块补匹配逻辑
- **建议映射的方法**：M-L2-04
- **风险**：中（`load_pages()` 仍通过输入适配模块串联修补链，拆分时必须保留现有导出与 patch 点）
- **验证**：AI 自证（跑全量 characterization tests）
- **范围**：约 3 文件 / 120 行迁移

### #2 保留主模块与输入适配模块的兼容导出 ✓

- **位置**：`mineru_to_docx.py:31-84`、`input_adapter_runtime.py:1-90`
- **分类**：结构
- **现状**：测试和主流程都仍从 `mineru_to_docx` 或 `input_adapter_runtime` 名字空间获取页面修补函数
- **问题**：如果直接删实现，现有 monkeypatch 和运行时绑定会失效
- **建议**：主模块改为直接从 `page_repair_runtime.py` 导出同名符号，输入适配模块仅复用这些导出以维持 `load_pages()` 默认路径
- **建议映射的方法**：M-L1-01
- **风险**：中（需要确保 `repair_and_sort_pages`、`merge_page_with_middle` 内部调用仍会回看主模块符号）
- **验证**：AI 自证（重点跑 `test_page_repair_characterization.py`）
- **范围**：约 3 文件 / 40 行

### #3 共享测试 helper 同步清理页面修补子模块缓存 ✓

- **位置**：`tests/test_render_table_from_html_characterization.py:117-124`
- **分类**：结构
- **现状**：共享 `_load_module()` 只会清理 `mineru_to_docx`、`input_adapter_runtime`、`render_config_runtime`、`text_rendering`
- **问题**：如果不加入 `page_repair_runtime`，多轮测试重载时会保留旧的运行时绑定
- **建议**：把 `page_repair_runtime` 一并加入模块清理列表
- **建议映射的方法**：M-L2-01
- **风险**：低（仅影响测试进程）
- **验证**：AI 自证（跑全量 characterization tests）
- **范围**：约 1 文件 / 1 行
