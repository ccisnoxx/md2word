---
doc_type: refactor-scan
refactor: 2026-05-16-text-normalization-split
status: user-reviewed
scope: "`mineru_to_docx.py` 中文本规范化、段落样式应用、正文/标题/TOC 段落填充链路，以及新增的 characterization tests"
summary: 发现 3 条优化点，结构 3 / 性能 0 / 可读性 0
---

# text-normalization-split scan

## 总览

- 扫描范围：`mineru_to_docx.py`、`tests/test_render_config_characterization.py`、`tests/test_text_render_characterization.py`
- 发现 3 条优化点：结构 3 / 性能 0 / 可读性 0
- 按风险：低 1 / 中 2 / 高 0
- 建议先做：#1 #2 #3
- 建议慎做 / 后做：无
- 前置检查 7 条全过：✓

## 条目

### #1 把公式与术语归一化链抽到独立模块 ✓

- **位置**：`mineru_to_docx.py:2418-2804`
- **分类**：结构
- **现状**：`normalize_formula_text`、`convert_inline_tex_to_html`、`prepare_text`、`render_inline_html_into_paragraph` 等 14 个函数与正则常量仍堆在主文件中
- **问题**：单文件 2982 行；同一职责链路跨越约 380 行，并被正文、TOC、表格运行时三处复用
- **建议**：新建独立文本渲染模块，承接公式归一化、术语替换和内联 markup 渲染
- **建议映射的方法**：M-L2-04
- **风险**：中（表格运行时通过回调依赖这组函数，迁移时要保持调用面不变）
- **验证**：AI 自证（跑 `test_render_table_from_html_characterization.py` 与新增文本链 characterization tests）
- **范围**：约 1 文件 380 行 + 1 新文件

### #2 把段落样式应用与标题/正文/列表/TOC 填充归并到文本模块 ✓

- **位置**：`mineru_to_docx.py:1985-2019`、`mineru_to_docx.py:2504-2957`
- **分类**：结构
- **现状**：TOC 段落填充、标题层级判断、样式应用、run 默认值设置和正文/列表填充混在主文件编排层里
- **问题**：页面编排层直接感知段落样式细节；同一文本职责散落在 TOC、正文和模板前言三个入口
- **建议**：将样式应用 helper 与 `fill_toc_*`、`fill_title_paragraph`、`fill_body_paragraph`、`fill_list_paragraph` 一并迁入文本模块
- **建议映射的方法**：M-L3-07
- **风险**：中（需要确保 `mineru_to_docx.py` 继续暴露同名调用面，避免测试和表格运行时受影响）
- **验证**：AI 自证（跑新增配置解析/文本渲染 characterization tests 与页面编排 characterization tests）
- **范围**：约 1 文件 260 行 + 1 新文件

### #3 通过主文件导入回填保持外部调用面不变 ✓

- **位置**：`mineru_to_docx.py:27-34`、`mineru_to_docx.py:1758-1768`、`mineru_to_docx.py:2162-2414`
- **分类**：结构
- **现状**：现有测试和表格运行时都直接从 `mineru_to_docx` 模块拿 `prepare_text`、`apply_named_style_config`、`fill_title_paragraph` 等函数
- **问题**：如果机械删除主文件实现，外部引用点会全部失效；这次目标是降单文件复杂度，不是改模块接口
- **建议**：在主文件顶层改为显式导入文本模块并继续以同名符号暴露，保持外部行为和导入面稳定
- **建议映射的方法**：M-L1-01
- **风险**：低（不改 CLI、数据结构和函数签名）
- **验证**：AI 自证（跑新增 characterization tests；确认 `mineru_to_docx` 仍能被现有测试按原方式 import）
- **范围**：约 1 文件 80 行
