# 现状度量（只读）

基线：`main@d45e46e1`，`app/domains/document_jobs/execution.py` 共 4128 行。以下数据由 AST 脚本和文本检索得到，未运行任何应用测试。行号均指该基线。

## 1. 迁出集合

`DocumentJobExecutionService` 中 1178–3144 行的方法，去掉 `_register_image_assets_archive`（只被 IR 转换调用，只用 `file_service`，留在宿主），加上 3145 行的 `_resolve_term_version_for_job`（只被翻译方法调用）。合计 34 个方法、1888 行；迁出后宿主约 2240 行。

模块级 `_TranslationBatchStorageError`、`_is_metadata_storage_error`（111–119 行）只被迁出集合使用，随之迁出。

| 起始行 | 行数 | 方法 |
|---:|---:|---|
| 1178 | 74 | `_ensure_translation_batches_and_enqueue` |
| 1253 | 15 | `_get_translation_execution_snapshot` |
| 1269 | 42 | `summarize_translation_generation` |
| 1312 | 50 | `_build_expected_translation_plans` |
| 1363 | 245 | `execute_translation_batch` |
| 1609 | 153 | `_claim_translation_batch` |
| 1763 | 41 | `_reconcile_translation_batch_atomic_rejection` |
| 1805 | 38 | `_fail_translation_batch_storage` |
| 1844 | 38 | `_mark_translating_started` |
| 1883 | 123 | `_handle_translation_batch_failure` |
| 2007 | 7 | `_should_split_translation_batch` |
| 2015 | 112 | `_split_translation_batch` |
| 2128 | 156 | `_finalize_translation_generation` |
| 2285 | 148 | `_register_translated_document_ir_and_continue` |
| 2434 | 19 | `_read_translation_artifact` |
| 2454 | 14 | `_read_translation_source` |
| 2469 | 23 | `_translation_integrity_binding` |
| 2493 | 75 | `_load_batch_replacements` |
| 2569 | 64 | `_register_translation_batch_result` |
| 2634 | 87 | `_enqueue_runnable_translation_batches` |
| 2722 | 19 | `_next_runnable_translation_batch` |
| 2742 | 59 | `_reset_expired_translation_batch_leases` |
| 2802 | 35 | `_cancel_translation_batch` |
| 2838 | 6 | `_provider_call_budget_remaining` |
| 2845 | 8 | `_provider_call_budget_remaining_for_batch` |
| 2854 | 8 | `_translation_batch_error_code` |
| 2863 | 13 | `_translation_profile_batch_limits` |
| 2877 | 49 | `_translation_profile_for_job` |
| 2928 | 12 | `_page_range_for_item_ids` |
| 2993 | 95 | `_translate_document_ir` |
| 3089 | 37 | `_record_translation_audit_events` |
| 3128 | 7 | `_recorder_call_log_file_ids` |
| 3137 | 7 | `_recorder_debug_archive_file_ids` |
| 3145 | 9 | `_resolve_term_version_for_job` |

## 2. 双向耦合

迁出集合调用宿主方法共 7 个、56 个调用点：

| 宿主方法 | 使用它的迁出方法数 | 性质 |
|---|---:|---|
| `_record_event` | 13 | 事件写入与安全投影 |
| `_mark_failed` | 9 | 任务失败收口（CAS） |
| `_fail_stage_attempt` | 3 | 按阶段快照归类失败 |
| `_get_uploaded_file` | 2 | 文件记录读取 |
| `_mark_timed_out_if_needed` | 1 | 超时收口 |
| `_document_ir_layout_metadata` | 1 | IR 诊断元数据 |
| `execute_job` | 1 | 翻译校验通过后续跑渲染（2282 行） |

宿主调用迁出集合共 3 个内部入口：

| 迁出方法 | 宿主调用方 |
|---|---|
| `_ensure_translation_batches_and_enqueue` | `execute_job`、`_convert_and_save_document_ir`、`_register_source_ir_and_enqueue_translation` |
| `_finalize_translation_generation` | `execute_job` |
| `_read_translation_source` | `execute_job`、`_convert_and_save_document_ir` |

实例属性：

- 迁出集合独占：`translation_batch_repository`、`document_ir_translation_service`、`translation_audit_service`、`term_version_service`、`translation_batch_task_queue`。
- 两侧共用：`settings`、`job_repository`、`file_service`、`job_resource_snapshot_service`。
- 迁出集合不使用 `logger`，范围内没有 `getattr(self, …)`、`type(self)`、`super()` 等动态查找。

## 3. 类外调用方

| 位置 | 调用 |
|---|---|
| `app/workers/document_tasks.py:38` | `runtime.document_job_execution_service.execute_translation_batch(...)` |
| `app/domains/document_jobs/router.py:396` | `runtime.document_job_execution_service.summarize_translation_generation(job, batches)` |
| `execution.py:4071`（`EagerDocumentTranslationBatchTaskQueue`） | `self.execution_service.execute_translation_batch(...)` |
| `app/main.py:218` | `document_job_execution_service.set_translation_batch_task_queue(...)` |

`DocumentJobExecutionService(...)` 的直接构造只有两处：`app/main.py:195`、`tests/test_fastapi_jobs_backend.py:494`。

## 4. 测试耦合

对迁出方法的引用 63 处（含 `patch.object(execution, "<名字>")`）：`execute_translation_batch` 45、`_finalize_translation_generation` 8、`_claim_translation_batch` 5、`_ensure_translation_batches_and_enqueue` 2、`_build_expected_translation_plans` 2、`_read_translation_source` 1。分布：`test_translation_batch_failure_semantics.py` 30、`test_translation_integrity_execution.py` 19、`test_document_job_execution_stages.py` 13、`test_degraded_page_display.py` 1。

对翻译专属属性的访问（按 `execution.<属性>` 检索，是下限）：`document_ir_translation_service` 30、`translation_batch_task_queue` 21、`translation_audit_service` 3。另有 8 处构造后重新赋值 `runtime.document_job_execution_service.document_ir_translation_service = …`（`test_fastapi_jobs_backend.py` 7 处、`test_document_job_delivery_state_api.py` 1 处）。

共用属性的构造后赋值 1 处：`tests/document_job_list_query_v2_publication_fixtures.py:151` 赋值 `execution.job_resource_snapshot_service`。

测试中按字符串路径打补丁的 `app.domains.document_jobs.execution.<名字>` 只有 `ensure_renderer_integrity`、`build_renderer_evidence`，都属渲染，不受迁出影响。`patch.object(execution, "execute_job")` 出现在 `test_document_job_execution_stages.py:329`、`:489`，用于拦截翻译收口后的续跑。

## 5. 其他发现

- `_translate_document_ir`（2993 行，95 行）在 `app/`、`tests/` 中按名字检索没有任何调用方。本任务不删除，原样搬移，是否删除另行决定。
- 当前只有主工作区，没有未合并到 `main` 的本地或远端分支。`11-02-poppler-readiness-degradation-policy`、`11-02-render-degradation-coverage` 的计划涉及 `execution.py` 的渲染段，不在迁出范围内。
- 既有规划：`.trellis/tasks/11-06-source-audit-remediation-plan/design.md:72-78`（B04）明确“暂不新增通用 StageContext、StageResult、插件框架”，后续拆分“依据试点复杂度和真实修改压力另定”。B04 试点已合入（提交 `7d753569`，`_failure_policy.py`）。
- `execution.py` 自 2026-08-01 以来改动 19 次。

## 6. 未核对

- 没有逐行阅读 34 个方法体，只读了 `_ensure_translation_batches_and_enqueue`、`summarize_translation_generation`、`execute_translation_batch` 开头和 `_finalize_translation_generation`。
- 没有运行测试，当前基线的通过/失败集合未知。B04 记录过 3 个与其无关的既有失败，具体用例需在实施时由基线运行确认。
- 测试耦合计数依赖变量命名（`execution`、`execution_service`、`runtime.document_job_execution_service`），其他别名下的访问可能漏计。
