# 现状度量

基线 `main@80032c25`（翻译批次提取 PR #39 合并后）。度量用 AST 统计 `app/domains/document_jobs/execution.py`，测试引用用 `git ls-files` 范围内的正则检索。

## 1. 宿主规模

`execution.py` 2164 行，`DocumentJobExecutionService` 51 个方法（104–2084 行）。阶段分发在 `execute_job`（154–207 行），渲染、质量检查、上传三个阶段都由一次调用进入：

```python
if latest.status == "running" and latest.stage in {"rendering", "quality_checking", "uploading"}:
    return self._render_and_save_word(latest, trace_id=trace_id)
```

## 2. 迁出集合

### 渲染核心（10 个方法，484 行）

| 方法 | 行 | 行数 |
|---|---|---|
| `_render_and_save_word` | 1195 | 229 |
| `_degrade_render_failure_page` | 1425 | 77 |
| `_finish_selected_or_current` | 1503 | 8 |
| `_finish_prepared_result` | 1512 | 56 |
| `_validate_render_result_file` | 1569 | 27 |
| `_validate_optional_block_anchors` | 1597 | 13 |
| `_get_existing_result_file` | 1751 | 40 |
| `_get_document_ir_file` | 1742 | 8 |
| `_build_image_loader` | 1895 | 20 |
| `_result_filename` | 1916 | 6 |

这 10 个方法在渲染段外唯一的调用方是 `execute_job` → `_render_and_save_word`。

### 表格占位符读取组（7 个方法，96 行）

`_load_placeholder_source`、`_get_placeholder_source_file`、`_read_current_placeholder_file`、`_ensure_placeholder_file_current`、`_ensure_placeholder_attempt_current`、`_read_placeholder_asset`、`_verify_placeholder_dependencies`（1792–1893 行）。

职责是表格占位图的源 PDF 与裁图资产完整性读取：按 ID 重取文件描述、核对生命周期与任务快照、读取前后各核验一次。组内不调用组外方法，只用 `file_repository`、`job_repository`、`file_service`。

组外调用：渲染核心 4 处（`_read_placeholder_asset`、`_verify_placeholder_dependencies`、`_ensure_placeholder_file_current`、`_load_placeholder_source`）；IR 转换 1 处，`_convert_and_save_document_ir` 第 837 行 `placeholder_source_loader=lambda: self._load_placeholder_source(job)`。

合计 17 个方法、580 行。迁出后宿主约 1580 行，新模块约 650 行（含导入与构造）。没有需要迁出的模块级定义。

## 3. 双向耦合

渲染段 → 宿主（20 个调用点，6 个方法）：

| 方法 | 调用数 | 宿主内其他调用方 |
|---|---|---|
| `_record_event` | 8 | MinerU、回调、IR 等 11 个方法 |
| `_mark_timed_out_if_needed` | 4 | `execute_job`、`_refresh_mineru_parse_attempt` |
| `_mark_failed` | 3 | `_fail_stage_attempt` 等 4 个方法 |
| `_get_uploaded_file` | 3 | `_run_mineru_parse`、`_get_mineru_raw_result_file` |
| `_mark_succeeded` | 1 | 无（仅渲染使用，但属于任务终态收口） |
| `_document_ir_layout_metadata` | 1 | IR 段 3 个方法 |

宿主 → 渲染段：`execute_job` → `_render_and_save_word`（1 处）、`_convert_and_save_document_ir` → `_load_placeholder_source`（1 处，位于 lambda 内，调用时才查找）。

翻译协作者 `translation_execution.py` 不引用渲染段的任何方法或属性；翻译收口后经宿主 `execute_job` 续跑渲染。

## 4. 依赖归属

| 依赖 | 渲染段 | 宿主其余方法 | 翻译协作者 |
|---|---|---|---|
| `word_renderer`、`template_read_service`、`word_preview_service` | 用 | 不用 | 不用 |
| `job_resource_snapshot_service` | 用 | 不用 | 用 |
| `settings`、`job_repository`、`file_repository`、`file_service`、`document_ir_service`、`logger` | 用 | 用 | `settings`、`job_repository`、`file_service` 用 |

`word_preview_service` 在宿主 `__init__` 中有默认构造（未传入时用 `settings`、`job_repository`、`event_repository`、`file_repository`、`file_service` 构造 `DocumentJobPreviewService`）。生产装配 `app/main.py:190` 构造同一个对象，同时传给执行服务和 `DocumentJobService`。

## 5. 模块级名字

仅渲染段使用、应随迁出的导入：`ApiError`、`DocumentIRAsset`、`DocumentIRRenderOptions`、`PAGE_RASTER_SOURCE_PATH`、`PdfCropSource`、`TableEvidenceError`、`TableReferenceProvenance`、`build_layout_plan`、`build_renderer_evidence`、`capture_render_publication_provenance`、`degradation_closure`、`drop_degraded_table_groups`、`ensure_renderer_integrity`、`has_evidence`、`image_evidence`、`placeholder_checksum`、`recheck_verified_report`、`replace_degraded_pages`、`save_report`、`time`、`validate_block_anchor_evidence`、`validate_candidate_binding`、`validate_persisted_render_evidence`、`validate_persisted_renderer_content`、`verify_report`。

两边共用：`Any`、`Callable`、`DocumentFileRecord`、`DocumentIR`、`DocumentIntegrityError`、`DocumentJobRecord`、`MinerUError`、`Path`、`SoftTimeLimitExceeded`、`TABLE_REFERENCE_ROLE`、`TablePlaceholderError`、`build_renderer_event_summary`、`decode_placeholders`、`decode_table_references`、`failure_policy`、`hashlib`、`is_translation_document_job_mode`、`utc_now`、`uuid4`。

## 6. 测试耦合

### 按模块路径打补丁（搬移即失效）

| 位置 | 目标 |
|---|---|
| `tests/test_document_job_execution_stages.py:192` | `app.domains.document_jobs.execution.ensure_renderer_integrity` |
| `tests/test_document_job_execution_stages.py:427` | `app.domains.document_jobs.execution.build_renderer_evidence` |
| `tests/test_document_job_execution_stages.py:534` | f-string `app.domains.document_jobs.execution.{target}`，循环 `build_renderer_evidence`、`ensure_renderer_integrity` |
| `tests/test_fastapi_jobs_backend.py:10677` | `app.domains.document_jobs.execution.ensure_renderer_integrity` |

这两个名字只被渲染段使用，搬移后宿主模块不再导入它们；`unittest.mock.patch` 对不存在的属性会抛 `AttributeError`，遗漏时会显式失败而不是静默失效。前提是宿主模块不能为了“兼容”保留这两个导入。

### 访问迁出方法（20 处）

- `_render_and_save_word`：点访问 4 处（`test_document_job_result_persistence.py`），`patch.object(execution, "_render_and_save_word", …)` 6 处（`test_degraded_page_display.py:102`、`test_document_job_execution_stages.py:67`、`test_document_job_result_persistence.py:548`、`:556`、`test_translation_integrity_execution.py:100`、`:149`）。
- `_build_image_loader` 5 处：`test_document_job_execution_stages.py` 1、`test_document_job_result_persistence.py` 3、`test_rnd503_dependency_integration.py` 1。
- `_get_document_ir_file` 3 处：上述三个文件各 1。
- `_get_existing_result_file` 2 处：`test_document_job_result_persistence.py`。

### 访问渲染专属属性（36 处）

- `word_renderer` 26 处：`test_document_job_execution_stages.py` 9（含 `patch.object(execution.word_renderer, …)` 4）、`test_document_job_result_persistence.py` 13（含 `new_execution` 2）、`test_rnd503_dependency_integration.py` 2、`test_fastapi_jobs_backend.py` 2。
- `template_read_service` 7 处：`test_degraded_page_display.py`、`test_document_job_execution_stages.py`、`test_rnd503_dependency_integration.py`、`test_translation_batch_failure_semantics.py`、`test_translation_integrity_execution.py` 各 1，`test_document_job_result_persistence.py` 2。均为读取。
- `word_preview_service` 3 处：`tests/document_job_list_query_v2_publication_fixtures.py:97-99`。

### 静默失效风险（赋值）

赋值不会报错，只会在宿主上多出没人读的属性：

- `tests/test_fastapi_jobs_backend.py:10543`、`:10580`：`runtime.document_job_execution_service.word_renderer = …`
- `tests/document_job_list_query_v2_publication_fixtures.py:152-153`：先给宿主赋 `job_resource_snapshot_service`，再同步到 `translation_batches`。迁出后宿主不再持有该依赖，需要改为同步到渲染协作者与翻译协作者。

读取与 `patch.object` 在迁出后会报 `AttributeError`，属于显式失败。

## 7. 经执行服务运行任务的测试模块

`test_fastapi_jobs_backend`、`test_document_job_result_persistence`、`test_translation_batch_failure_semantics`、`test_document_job_execution_stages`、`test_database_job_repository`、`test_translation_integrity_execution`、`test_mineru_download_boundary`、`test_page_degradation`、`test_image_pdf_fallback`、`test_table_placeholder_failure_context`、`test_image_normalization_pipeline`、`test_document_job_delivery_state_api`、`test_degraded_page_display`、`test_rnd503_dependency_integration`、`test_render_page_degradation`、`test_document_job_modes`、`test_document_job_list_query_v2_service`、`test_document_job_failure_diagnostic`；以及导入发布夹具的 `test_document_job_list_query_v2_writers`、`test_document_job_incident_publish_light_check`、`test_document_job_list_publish_light_check`。

上一任务基线里 `test_document_job_execution_stages` 已有 5 个 `_build_image_loader() missing 1 required positional argument: 'document_ir'` 错误（测试按旧签名调用），属于既有问题。

## 8. 相关任务与文档

- `11-02-render-degradation-coverage`（扩大页面降级覆盖面）状态仍为 `in_progress`，但代码已合入 `main`（`3b64b63e`，后续 `79f20cef` 把重试上限改为 `settings.render_degradation_max_attempts`）。没有并行代码冲突，只是任务记录未归档。
- `.trellis/spec/backend/word-generation-rules.md:8`、`:42` 把 `_render_and_save_word` 的 owner 写为 `execution.py::DocumentJobExecutionService`，迁出后要更新。该文件当前有另一会话的 1 行未提交改动，实施时需避开或等其落地。
- `.trellis/spec/backend/directory-structure.md` 的 `document_jobs/` 文件列表要加入新模块。
- `.trellis/spec/backend/logging-guidelines.md:9` 只把 `execution.py` 列为证据文件，不是 owner 表述，不需要改。
- `.trellis/spec/backend/document-job-mode-contract.md:73` 写“推进和事件 owner 为 `execution.py`”。阶段推进与事件收口仍在宿主，保持成立。
