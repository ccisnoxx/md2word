# 来源账本 v2 与注释账本提交计划

已确认并执行。工作提交 `29592706baa1e6ed60431b9ce1d838c516f30be2` 基于 `57772613`，包含 35 个实现文件、8 个测试文件和 2 份规范。新增的实现文件是 `app/services/document_ir/source_item_ledger.py`，其余 44 个文件为修改。

## 提交信息

```text
fix: 校验列表项与注释的来源完整性
```

## 已提交的 45 个路径

### MinerU 转换与 DocumentIR 账本（8）

- `app/conversion/docx_rules/mineru_content.py`
- `app/services/document_ir/caption_reconciler.py`
- `app/services/document_ir/integrity.py`
- `app/services/document_ir/mineru_converter.py`
- `app/services/document_ir/models.py`
- `app/services/document_ir/page_degradation.py`
- `app/services/document_ir/source_item_ledger.py`
- `app/services/document_ir/table_annotations.py`

### 翻译回填与批次收口（6）

- `app/domains/translation/document_ir_translator.py`
- `app/domains/document_jobs/translation_execution/artifacts.py`
- `app/domains/document_jobs/translation_execution/failure.py`
- `app/domains/document_jobs/translation_execution/generation.py`
- `app/domains/document_jobs/translation_execution/planning.py`
- `app/domains/document_jobs/translation_execution/provider_call.py`

### Word 渲染与持久化证据（12）

- `app/services/renderer/block_evidence.py`
- `app/services/renderer/content_contract.py`
- `app/services/renderer/image_evidence.py`
- `app/services/renderer/layout_plan.py`
- `app/services/renderer/logical_table_plan.py`
- `app/services/renderer/native_table_renderer.py`
- `app/services/renderer/render_event_summary.py`
- `app/services/renderer/render_evidence.py`
- `app/services/renderer/render_evidence_validation.py`
- `app/services/renderer/render_plan.py`
- `app/services/renderer/render_preparation.py`
- `app/services/renderer/word_renderer.py`

### 任务质量、复核与读取边界（9）

- `app/domains/document_jobs/_failure_policy.py`
- `app/domains/document_jobs/base_quality.py`
- `app/domains/document_jobs/preview_evidence.py`
- `app/domains/document_jobs/render_result.py`
- `app/domains/document_jobs/review.py`
- `app/domains/document_jobs/review_content.py`
- `app/domains/document_jobs/table_evidence.py`
- `app/domains/document_jobs/use_cases/table_references.py`
- `app/domains/document_jobs/use_cases/translation_qa.py`

### 定向回归（8）

- `tests/test_document_ir_layout_contract.py`
- `tests/test_document_ir_mineru_converter_layout.py`
- `tests/test_document_ir_translation.py`
- `tests/test_document_job_review_blocks_api.py`
- `tests/test_formal_mineru_render_evidence.py`
- `tests/test_mineru_artifact_validator.py`
- `tests/test_preview_page_mapping.py`
- `tests/test_translation_integrity_execution.py`

### Trellis 规范（2）

- `.trellis/spec/backend/translation-integrity-validator.md`
- `.trellis/spec/backend/word-generation-rules.md`

## 排除范围

direct 克隆 MinerU 语言任务的 4 个已跟踪文件和 7 份任务文件留在工作区。

- `.trellis/spec/backend/document-job-mode-contract.md`
- `app/domains/document_jobs/use_cases/request_snapshot.py`
- `app/domains/document_jobs/use_cases/submission.py`
- `tests/test_document_job_modes.py`
- `.trellis/tasks/11-17-direct-clone-mineru-language/` 下全部任务文件。

本任务的规划、上下文、任务状态、验收和基线记录随独立的归档提交保存。

## 提交验证

已核对工作提交的 45 个路径与确认清单一致。提交时复用了现有定向测试结果，未推送。两项独立降级失败已在干净基线复现并另记。见[验收记录](validation.md)和[基线失败记录](baseline-failures.md)。
