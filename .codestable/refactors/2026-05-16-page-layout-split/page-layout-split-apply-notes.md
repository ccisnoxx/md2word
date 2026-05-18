---
doc_type: refactor-apply-notes
refactor: 2026-05-16-page-layout-split
---

# page-layout-split apply notes

## 步骤 1: 抽出页面编排运行时模块

- 完成时间: 2026-05-16
- 改动文件: `page_layout_runtime.py`, `mineru_to_docx.py`
- 验证结果: `python3 -m py_compile mineru_to_docx.py input_adapter_runtime.py page_repair_runtime.py render_config_runtime.py text_rendering.py page_layout_runtime.py tests/test_render_table_from_html_characterization.py tests/test_page_layout_characterization.py` 通过
- 偏离: 无

## 步骤 2: 主文件保留兼容导出与运行时绑定

- 完成时间: 2026-05-16
- 改动文件: `mineru_to_docx.py`
- 验证结果: `test_page_layout_characterization.py`、`test_render_table_from_html_characterization.py` 随全量 characterization tests 一起通过
- 偏离: 无

## 步骤 3: 共享测试 helper 同步清理 page-layout 子模块

- 完成时间: 2026-05-16
- 改动文件: `tests/test_render_table_from_html_characterization.py`
- 验证结果: `_load_module()` 新增 `page_layout_runtime` 后，多轮重载仍稳定
- 偏离: 无

## 步骤 4: 跑全量 characterization tests

- 完成时间: 2026-05-16
- 改动文件: 无
- 验证结果: `env PYTHONPATH=/Users/sc/MinerU/md2word_file/tests /Users/sc/miniconda3/envs/md2word/bin/python -m unittest discover tests -p 'test_*characterization.py'` 通过
- 偏离: 无
