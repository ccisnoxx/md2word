---
doc_type: refactor-scan
refactor: 2026-05-16-page-layout-split
status: user-reviewed
scope: "`mineru_to_docx.py` 中剩余的页面编排链，以及共享 characterization test helper 的模块重载入口"
summary: 发现 3 条优化点，结构 3 / 性能 0 / 可读性 0
---

# page-layout-split scan

## 总览

- 扫描范围：`mineru_to_docx.py`、`page_layout_runtime.py`、`tests/test_page_layout_characterization.py`、`tests/test_render_table_from_html_characterization.py`
- 发现 3 条优化点：结构 3 / 性能 0 / 可读性 0
- 按风险：低 1 / 中 2 / 高 0
- 建议先做：#1 #2 #3
- 建议慎做 / 后做：无
- 前置检查 7 条全过：✓

## 条目

### #1 把页面编排链从主文件独立成新模块 ✓

- **位置**：`mineru_to_docx.py:572-1144`
- **分类**：结构
- **现状**：主文件剩余的大块职责主要是文档编排、TOC 判定、单双栏布局和视觉块分发
- **问题**：主文件仍然承担文档生命周期编排与视觉块容器分发两类高层职责，约 570 行逻辑集中在一起
- **建议**：新建 `page_layout_runtime.py`，迁移 `build_document`、`render_document_page`、`render_page_body`、`build_regions`、`render_visual_block` 等页面编排函数
- **建议映射的方法**：M-L2-04
- **风险**：中（页面编排链直接调用表格渲染和文本渲染，运行时绑定漏一处就会让 patch 点失效）
- **验证**：AI 自证（跑全量 characterization tests，重点看页面编排与表格渲染）
- **范围**：约 2 文件 / 570 行迁移

### #2 保留主模块的页面编排导出与 monkeypatch 兼容面 ✓

- **位置**：`tests/test_page_layout_characterization.py:108-167`、`mineru_to_docx.py:540-1144`
- **分类**：结构
- **现状**：测试会 patch `create_document`、`clear_document_body`、`configure_section`、`render_toc_page`、`render_page_body`、`render_one_col_region`、`render_two_col_region`
- **问题**：如果主文件直接删除这些页面编排函数或让它们在新模块内部互相直连，现有 characterization tests 会打不中 patch 点
- **建议**：主文件继续导出同名函数；`page_layout_runtime.py` 通过运行时绑定回看主模块符号
- **建议映射的方法**：M-L1-01
- **风险**：中（`build_document`、`render_document_page_body`、`render_page_body` 三层都要通过运行时查找调用）
- **验证**：AI 自证（重点跑 `test_page_layout_characterization.py`）
- **范围**：约 2 文件 / 80 行

### #3 共享测试 helper 同步清理页面编排子模块缓存 ✓

- **位置**：`tests/test_render_table_from_html_characterization.py:117-124`
- **分类**：结构
- **现状**：共享 `_load_module()` 已清理输入适配、页面修补、配置、文本模块，但还不知道新的 `page_layout_runtime`
- **问题**：如果不加入模块清理列表，多轮重载时页面编排模块会保留旧的运行时绑定
- **建议**：把 `page_layout_runtime` 一并加入共享 helper 的模块清理列表
- **建议映射的方法**：M-L2-01
- **风险**：低（仅影响测试进程）
- **验证**：AI 自证（跑全量 characterization tests）
- **范围**：约 1 文件 / 1 行
