---
doc_type: refactor-apply-notes
refactor: 2026-05-16-pagination-flow-relax
---

# pagination-flow-relax apply notes

## 步骤 1: 抽出 section 创建决策函数

- 完成时间: 2026-05-16
- 改动文件: `page_layout_runtime.py`, `tests/test_page_layout_characterization.py`
- 验证结果: 新增 `should_start_new_section()` / `is_landscape_page()`，相关 characterization tests 通过
- 偏离: 无

## 步骤 2: 把页面编排改成条件分页

- 完成时间: 2026-05-16
- 改动文件: `page_layout_runtime.py`, `mineru_to_docx.py`
- 验证结果: `python3 -m py_compile mineru_to_docx.py input_adapter_runtime.py page_repair_runtime.py render_config_runtime.py text_rendering.py page_layout_runtime.py tests/test_page_layout_characterization.py tests/test_text_render_characterization.py` 通过
- 偏离: 封面与目录会连续流排，不再天然按源页硬切，这是本次预期行为变化

## 步骤 3: 回归目录页、长表页和真实样例空白页

- 完成时间: 2026-05-16
- 改动文件: `template_configs/datasheet_template.yaml`, `text_rendering.py`, `page_layout_runtime.py`, `tests/test_page_layout_characterization.py`
- 验证结果: `env PYTHONPATH=/Users/sc/MinerU/md2word_file/tests /Users/sc/miniconda3/envs/md2word/bin/python -m unittest discover tests -p 'test_*characterization.py'` 通过；真实样例重新生成为 `out_file/CWQ2P690T-visual-check.docx`
- 偏离: 为恢复常规 Word 排版，同时补了正文首行两个汉字缩进、标题/图注/表注/表格正文的显式样式项；目录起始页与目录结束后的正文起始页重新加回强制分页，避免目录和正文流到同一页

## 步骤 4: 附录起始页与长表续页再调优

- 完成时间: 2026-05-16
- 改动文件: `page_layout_runtime.py`, `table_long_renderer.py`, `tests/test_page_layout_characterization.py`, `tests/test_render_table_from_html_characterization.py`
- 验证结果: 全量 characterization tests 提升到 `58` 项并全部通过；真实样例再次重生成到 `out_file/CWQ2P690T-visual-check.docx`
- 偏离: 附录标题页显式强制新页；长表续页容量继续扣除续表标题高度，并收紧表格行高估算，以减少页底空白
