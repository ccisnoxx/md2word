# 实施计划

1. 基线：`test_mineru_artifact_validator`、`test_image_pdf_fallback`、`test_image_normalization_pipeline`、`test_document_job_failure_diagnostic`、`test_bbox_coordinate_space`、`test_document_ir_mineru_converter_layout`、`test_render_failure_context`、`test_document_job_delivery_state_api`。
2. 栅格器与装配 → 验证器推迟 → 转换器降级与闭包 → 对账 → 资产登记。
3. 新测试 `tests/test_page_degradation.py`（design 第 6 节）。
4. 真实样本目视（`tests/tmp/`，不入库）。
5. 规格：INPUT-002、IR-002/IR-004、QUALITY 相关条目补充降级合同。
6. 回归对比。

## 实施结果与验证（2026-11-02）

- 代码：`pdf_crop.PopplerPdfPageRasterizer`（与裁切器共用 `_run_poppler`）、`table_placeholder.PdfPageRasterizer` 协议、`artifact_validator` 推迟表格问题与 `restore_deferred_fatal`、`mineru_converter._degrade_pages/_degradation_closure`、`models.DocumentIRMetadata.degraded_pages`、`integrity` 扣除降级源块、`logical_table_group` 排除合成块、`execution` 登记 `origin=pdf_page_raster`、`main.py` 装配。
- 设计偏差：降级前提（无页码、无栅格器、无源 PDF 加载器、超过阈值）在构建 IR 块之前检查，保证不满足时与现状一样在 IR 构建前带报告失败；推迟表格问题只针对仍在有效指针集合中的块，被续表归一化合并掉的块照旧中止。
- 实施中修复：① 前提检查后置导致 `test_unconsumable_html_stops_before_ir_construction_with_report` 失败 → 前移；② 被合并块的无效 HTML 被静默推迟 → 限定有效指针；③ 合成块在 `validate_logical_table_groups` 中 `KeyError 'mineru_source'` → `body_sources` 排除合成块。
- 新测试 `tests/test_page_degradation.py` 6 项通过（表格降级、图片回退失败降级、4 种前提不满足整体失败、闭包两项、eager 端到端 blocked/internal_draft/批准被拒/DOCX 含整页图与提示）；`test_image_pdf_fallback` 中“其他中止错误”用例改用无页码表格以保持原语义。
- 回归：实施计划第 1 步 8 个模块共 223 项，失败/错误集合与基线一致（均为既有失败：delivery_state_api 夹具、表格占位验证、`test_renderer_evidence_blocks_missing_layout_drawing_and_table` 的 `table_html_unsupported_structure`），未新增失败。
- 真实 Poppler：OPA228 P1 两页样本（v2 content list）人为破坏第 2 页表格 HTML → 第 2 页降级（移除 14 个源块），报告 `can_convert=True`、`invalid_table_html` 为非中止 blocker；DOCX 含提示与整页图像，第 1 页正文可编辑；整页图像（1224×1584）目视正确。
