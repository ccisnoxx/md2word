---
doc_type: refactor-apply-notes
refactor: 2026-05-16-text-normalization-split
---

# text-normalization-split apply notes

## 步骤 1: 固化配置解析与文本渲染现状测试

- 完成时间: 2026-05-16
- 改动文件: `tests/test_render_config_characterization.py`, `tests/test_text_render_characterization.py`
- 验证结果: `env PYTHONPATH=/Users/sc/MinerU/md2word_file/tests TMPDIR=/Users/sc/MinerU/md2word_file/tests/.tmp /Users/sc/miniconda3/envs/md2word/bin/python -m unittest discover tests -p 'test_render_*characterization.py'` 通过
- 偏离: 无

## 步骤 2: 抽出独立文本渲染模块

- 完成时间: 2026-05-16
- 改动文件: `text_rendering.py`, `mineru_to_docx.py`
- 验证结果: `python3 -m py_compile mineru_to_docx.py text_rendering.py tests/test_render_config_characterization.py tests/test_text_render_characterization.py` 通过
- 偏离: 为保持现有 monkeypatch 兼容性，在 `text_rendering.py` 增加 `bind_runtime()` 和运行时符号解析

## 步骤 3: 主文件改为导入并保持同名调用面

- 完成时间: 2026-05-16
- 改动文件: `mineru_to_docx.py`
- 验证结果: `env PYTHONPATH=/Users/sc/MinerU/md2word_file/tests TMPDIR=/Users/sc/MinerU/md2word_file/tests/.tmp /Users/sc/miniconda3/envs/md2word/bin/python -m unittest test_render_table_from_html_characterization test_render_config_characterization test_text_render_characterization test_page_layout_characterization test_page_repair_characterization` 通过
- 偏离: 无

## 步骤 4: 相关测试与元数据校验

- 完成时间: 2026-05-16
- 改动文件: `.codestable/refactors/2026-05-16-text-normalization-split/*`
- 验证结果: `validate-yaml.py` 已通过 design 与 checklist；scan 修正后待复跑确认
- 偏离: 现有 `tests/test_input_adapter_characterization.py` 中 11 个用例依赖 `tempfile.TemporaryDirectory()`，在当前沙箱内会因禁止创建临时目录而失败，未纳入本次可执行验证
