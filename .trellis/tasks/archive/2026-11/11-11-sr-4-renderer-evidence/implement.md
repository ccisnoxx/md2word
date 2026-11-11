# 实施计划

## 检查清单

- [x] 0. 编写 `verify_render_equivalence.py`，在基线上运行两次确认稳定，保存 `validation/baseline-parts.json`；记录定向测试的基线结果。
  - 输入：2 个提交的组件样本 + 主仓库本地 `mineru_result/` 下 6 个包（gitignore，只读传入；其中 1 个在基线上就以 `TableRenderError` 失败，失败消息也参与对比）。用法见 `validation/equiv.sh`。
  - 不稳定来源与处理：`zipfile.writestr` 按秒写入条目时间，导致整包 `docx_sha256` 及其派生的 `evidence_sha256`、`coverage_sha256`、`report_sha256` 随运行时刻变化。脚本只替换 `zipfile` 模块看到的 `localtime`，不排除任何 part。`renderer_metadata` 中由 set 生成的列表顺序随哈希种子变化，`equiv.sh` 固定了 `PYTHONHASHSEED=0`。修正后连续 3 次运行结果完全一致。
  - 定向测试基线：401 项，历史失败 132 项（`validation/baseline-failset.txt`）。
- [x] 1. 拆分 evidence 三个模块，更新导入方（实际 29 个），删除 `evidence.py`。完整定向测试的失败集合与基线一致，等价性一致。实际放置位置与依赖方向见 design §1“实施结果”。
- [x] 2. 拆分 `render_to_result`（新增 `render_preparation.py`）。三个模块 0 失败，与基线相同；等价性一致。`render_to_result` 现为 27 行。`_source_page_context`、`_attach_plan_failure_context` 随计划阶段迁到 `render_preparation.py`，`test_render_failure_context` 的 patch 目标字符串改为新模块。
- [x] 3. 迁出 `WordPageLayoutMixin`（`page_layout_renderer.py`，A4 默认尺寸常量随之迁出）。检查结果同上，等价性一致。
- [x] 4. 迁出 `WordFormulaRendererMixin`（`formula_renderer.py`）和 `WordListNumberingMixin`（`list_numbering.py`）。`image_evidence.py` 原来单独实例化 `WordTextRendererMixin` 重放题注，这条路径依赖已迁出的 `_add_complex_field`、`_render_mixed_math`，因此改用私有组合类 `_AnnotationTextRenderer(WordTextRendererMixin, WordFormulaRendererMixin)`。`test_formula_*`、`test_document_ir_word_renderer_layout`、`test_image_group_rendering` 的失败集合与基线一致，等价性一致。
- [x] 5. 迁出 `WordNativeTableRendererMixin`（`native_table_renderer.py`，含 `NativeCellPart`、`native_cell_parts`、`_format_table_cell`）。`content_contract.py` 中的延迟导入改为新路径；`_render_table_placeholders` 也被非原生表格路径使用，所以保留在 `table_renderer.py`。检查结果同上，等价性一致。
- [x] 6. 更新 `word-generation-rules.md` 与 `error-handling.md` 中的路径 owner，并顺带修正 5 个能一一对应的过时符号名。`wc -l` 显示本任务涉及的模块都不超过 550 行；超出的 `content_contract.py`（582 行）和 `render_plan.py`（556 行）本次未改结构，不在拆分范围内。`trellis-check` 在本会话不可用，未运行，改为执行下面的最终检查。
  - 最终检查：完整定向测试集合 401 项，失败集合与基线一致（132 项历史失败，无新增，见 `validation/final.actual`）；8 个样本的等价性对比与基线完全一致；`rg "renderer\.evidence\b|renderer import evidence" app tests scripts` 结果为 0。
  - 方法级逐字核对：HEAD 中 `word_renderer`、`text_renderer`、`table_renderer` 的全部方法与模块级定义在新位置源码逐字一致，只有 `render_to_result` 按设计改写；42 个 evidence 顶层定义也逐字一致。各 Mixin 之间没有同名方法。
  - spec 中仍有 3 个历史遗留的过时符号，与本次重构无关，没有明确的对应实现，未修改：`text_renderer.py::_fill_auto_list_or_paragraph`、`::_fill_toc_entry_if_needed`、`word_renderer.py::_RenderContext.toc_written`。
- 提交：按会话约定，所有提交都等用户确认提交计划后再进行。

## 冲突说明

第 1 步会修改 `execution.py`、`render_execution.py`、`router.py`、`preview.py` 等文件的 import 行，与 sr-1、sr-2 有重叠。如果它们先合入，rebase 时只处理 import 行，不夹带其他改动。

## 回滚点

每一步一次提交，互相独立（第 2 步依赖第 1 步中 `render_contract_failure` 的新路径）。

## 定向测试集合

`tests.test_document_ir_word_renderer_layout tests.test_document_ir_mineru_converter_layout tests.test_formula_rendering tests.test_formula_rendering_compatibility tests.test_formula_literal_support tests.test_image_group_rendering tests.test_two_column_reading_order tests.test_parameter_paragraph_line_breaks tests.test_render_failure_context tests.test_render_page_degradation tests.test_document_ir_layout_contract tests.test_mineru_artifact_validator tests.test_document_job_result_persistence tests.test_document_job_execution_stages tests.test_document_job_delivery_state tests.test_rnd503_dependency_integration tests.test_component_pdf_sample_governance tests.test_conversion_sandbox_dev_tools`
