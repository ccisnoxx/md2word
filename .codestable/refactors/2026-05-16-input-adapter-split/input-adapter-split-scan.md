---
doc_type: refactor-scan
refactor: 2026-05-16-input-adapter-split
status: user-reviewed
scope: "`mineru_to_docx.py` 中的输入适配链，以及共享 characterization test helper 的模块重载入口"
summary: 发现 3 条优化点，结构 3 / 性能 0 / 可读性 0
---

# input-adapter-split scan

## 总览

- 扫描范围：`mineru_to_docx.py`、`input_adapter_runtime.py`、`tests/test_input_adapter_characterization.py`、`tests/test_render_table_from_html_characterization.py`
- 发现 3 条优化点：结构 3 / 性能 0 / 可读性 0
- 按风险：低 1 / 中 2 / 高 0
- 建议先做：#1 #2 #3
- 建议慎做 / 后做：无
- 前置检查 7 条全过：✓

## 条目

### #1 把输入适配链抽到独立模块 ✓

- **位置**：`mineru_to_docx.py:433-1299`
- **分类**：结构
- **现状**：输入物料化、JSON 解析、视觉块归一化、middle 回填、资产路径解析全部堆在主文件中
- **问题**：单文件同时承担 CLI、配置、输入适配、页面修补、页面编排、渲染 6 类职责；输入链单独约 800 行
- **建议**：新建 `input_adapter_runtime.py`，承接输入物料化、内容页装载、middle 页装载、块解析和资产路径归一化逻辑
- **建议映射的方法**：M-L2-04
- **风险**：中（现有测试和页面修补链会直接引用这些函数名，拆分后必须保留兼容面）
- **验证**：AI 自证（跑全量 characterization tests）
- **范围**：约 2 文件 / 800 行迁移

### #2 保留主模块的输入链导出与内部 patch 点 ✓

- **位置**：`tests/test_page_repair_characterization.py:91-118`、`tests/test_input_adapter_characterization.py:15-358`
- **分类**：结构
- **现状**：测试通过 `mineru_to_docx` 顶层函数名调用或 patch `load_content_pages`、`load_middle_pages`
- **问题**：如果主文件直接删掉这些符号，`load_pages()` 等内部链路会绕过 patch，导致 characterization tests 失效
- **建议**：主文件继续导出同名函数；输入模块内部通过运行时绑定回看主模块符号
- **建议映射的方法**：M-L1-01
- **风险**：中（需要保证 `load_pages`、`build_v2_pages`、`parse_v2_block` 等内部调用都能回到主模块符号）
- **验证**：AI 自证（重点跑 `test_input_adapter_characterization.py` 和 `test_page_repair_characterization.py`）
- **范围**：约 2 文件 / 80 行

### #3 共享测试 helper 同步清理输入适配子模块缓存 ✓

- **位置**：`tests/test_render_table_from_html_characterization.py:117-124`
- **分类**：结构
- **现状**：共享 `_load_module()` 已会清理 `text_rendering` 和 `render_config_runtime`，但还不知道新的 `input_adapter_runtime`
- **问题**：如果不一起清理，输入模块会沿用上一轮导入时的依赖和运行时绑定，characterization tests 可能读到旧状态
- **建议**：把 `input_adapter_runtime` 一并加入共享 helper 的模块清理列表
- **建议映射的方法**：M-L2-01
- **风险**：低（仅影响测试进程）
- **验证**：AI 自证（跑全量 characterization tests）
- **范围**：约 1 文件 / 1 行
