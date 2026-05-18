---
doc_type: refactor-apply-notes
refactor: 2026-05-16-page-repair-split
---

# page-repair-split apply notes

## 步骤 1: 抽出页面修补运行时模块

- 完成时间: 2026-05-16
- 改动文件: `page_repair_runtime.py`, `input_adapter_runtime.py`
- 验证结果: `python3 -m py_compile mineru_to_docx.py input_adapter_runtime.py page_repair_runtime.py render_config_runtime.py text_rendering.py tests/test_render_table_from_html_characterization.py tests/test_input_adapter_characterization.py tests/test_page_repair_characterization.py` 通过
- 偏离: 无

## 步骤 2: 更新主模块与输入适配模块的兼容导出

- 完成时间: 2026-05-16
- 改动文件: `mineru_to_docx.py`, `input_adapter_runtime.py`
- 验证结果: `test_page_repair_characterization.py`、`test_input_adapter_characterization.py` 随全量 characterization tests 一起通过
- 偏离: 无

## 步骤 3: 共享测试 helper 同步清理 page-repair 子模块

- 完成时间: 2026-05-16
- 改动文件: `tests/test_render_table_from_html_characterization.py`
- 验证结果: `_load_module()` 新增 `page_repair_runtime` 后，多轮重载仍稳定
- 偏离: 无

## 步骤 4: 跑全量 characterization tests

- 完成时间: 2026-05-16
- 改动文件: 无
- 验证结果: `env PYTHONPATH=/Users/sc/MinerU/md2word_file/tests /Users/sc/miniconda3/envs/md2word/bin/python -m unittest discover tests -p 'test_*characterization.py'` 通过
- 偏离: 无
