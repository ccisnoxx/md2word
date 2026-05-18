---
doc_type: refactor-apply-notes
refactor: 2026-05-16-config-runtime-split
---

# config-runtime-split apply notes

## 步骤 1: 抽出配置运行时模块

- 完成时间: 2026-05-16
- 改动文件: `render_config_runtime.py`, `mineru_to_docx.py`
- 验证结果: `python3 -m py_compile mineru_to_docx.py render_config_runtime.py text_rendering.py tests/test_render_table_from_html_characterization.py tests/test_render_config_characterization.py tests/test_text_render_characterization.py tests/test_input_adapter_characterization.py` 通过
- 偏离: 为兼容主模块 patch 点，在 `render_config_runtime.py` 增加 `bind_runtime()` 和运行时符号解析

## 步骤 2: 主文件保留兼容导出与薄包装

- 完成时间: 2026-05-16
- 改动文件: `mineru_to_docx.py`
- 验证结果: `test_render_config_characterization.py` 已包含对 `find_layout_config_path`、`load_section_layout`、`load_paragraph_styles`、`TerminologyReplacer` 的 patch 验证，并随全量套件一起通过
- 偏离: 主模块补回 `yaml` 与 `BeautifulSoup` 顶层符号，以兼容现有测试 patch 方式

## 步骤 3: 修复共享测试 helper 的 tempfile 与模块重载入口

- 完成时间: 2026-05-16
- 改动文件: `tests/test_render_table_from_html_characterization.py`
- 验证结果: `test_input_adapter_characterization.py` 不再因 `TemporaryDirectory()` 默认目录不可写失败
- 偏离: 无

## 步骤 4: 跑全量 characterization tests

- 完成时间: 2026-05-16
- 改动文件: 无
- 验证结果: `env PYTHONPATH=/Users/sc/MinerU/md2word_file/tests /Users/sc/miniconda3/envs/md2word/bin/python -m unittest discover tests -p 'test_*characterization.py'` 通过
- 偏离: 无
