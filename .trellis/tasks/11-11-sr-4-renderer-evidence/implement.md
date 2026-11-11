# 实施计划

## 检查清单

- [ ] 0. 编写 `verify_render_equivalence.py`，在基线上运行两次确认稳定，保存 `validation/baseline-parts.json`；记录定向测试的基线结果。
- [ ] 1. 拆分 evidence 三个模块，更新 31 个导入方，删除 `evidence.py`。检查：完整定向测试集合 + 等价性对比。提交。
- [ ] 2. 拆分 `render_to_result`（新增 `render_preparation.py`）。检查：`test_document_ir_word_renderer_layout`、`test_render_failure_context`、`test_render_page_degradation` + 等价性对比。提交。
- [ ] 3. 迁出 `WordPageLayoutMixin`。检查：同上。提交。
- [ ] 4. 迁出 `WordFormulaRendererMixin` 和 `WordListNumberingMixin`。检查：`test_formula_*`、`test_document_ir_word_renderer_layout` + 等价性对比。提交。
- [ ] 5. 迁出 `WordNativeTableRendererMixin`。检查：`test_document_ir_word_renderer_layout`、`test_document_ir_mineru_converter_layout` + 等价性对比。提交。
- [ ] 6. 更新 `word-generation-rules.md` 中的路径 owner；`wc -l app/services/renderer/*.py` 确认没有超过上限的模块；运行 `trellis-check`。提交。

## 冲突说明

第 1 步会修改 `execution.py`、`render_execution.py`、`router.py`、`preview.py` 等文件的 import 行，与 sr-1、sr-2 有重叠。如果它们先合入，rebase 时只处理 import 行，不夹带其他改动。

## 回滚点

每一步一次提交，互相独立（第 2 步依赖第 1 步中 `render_contract_failure` 的新路径）。

## 定向测试集合

`tests.test_document_ir_word_renderer_layout tests.test_document_ir_mineru_converter_layout tests.test_formula_rendering tests.test_formula_rendering_compatibility tests.test_formula_literal_support tests.test_image_group_rendering tests.test_two_column_reading_order tests.test_parameter_paragraph_line_breaks tests.test_render_failure_context tests.test_render_page_degradation tests.test_document_ir_layout_contract tests.test_mineru_artifact_validator tests.test_document_job_result_persistence tests.test_document_job_execution_stages tests.test_document_job_delivery_state tests.test_rnd503_dependency_integration tests.test_component_pdf_sample_governance tests.test_conversion_sandbox_dev_tools`
