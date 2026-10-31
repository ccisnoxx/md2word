# Error Handling

## 正式翻译完整性错误

`TranslationIntegrityError` 只携带固定中文消息、稳定 `code` 和脱敏 `evidence`，没有 partial replacements。具体错误矩阵见 [翻译完整性合同](translation-integrity-validator.md)。同步 `DocumentIRTranslationError` 保留 code/evidence；Worker 在通用 ValueError 映射前识别完整性错误，批次保留专用码，主任务顶层仍为既有 `translation_failed`。Provider JSON/传输/截断保留原分类，不把完整性失败伪装成截断。

外部 Provider 的任意异常不能直接以 `str(error)` 或原异常链进入普通日志、job event 或审计；边界输出固定安全描述及允许的类型/状态/usage/hash 元数据。只替换已知 Prompt 字符串不足以保证脱敏。真实调用只记一次成功/失败审计，调用前验证失败不伪造调用；审计写失败保持可见，不能吞掉后标记成功或再次伪造一次 Provider 失败审计。

首次计划尚无 batch 时的预算错误同样保留顶层 `translation_failed`，通过既有 `stage_failed.payload.integrity` 留下专用机器码与安全摘要；没有 batch 的 binding 为 null，不创建假的调用日志或批次。普通非翻译错误与条件状态更新不改变。

批次终态、树损坏和 attempt/lease 停止原因由 [批次生命周期合同](translation-batch-lifecycle.md#4-校验与错误矩阵) 定义：叶子终败立即归 `translating/translation_failed`，不等待兄弟或改记质量 blocked；fan-in 来源/完整性问题归 `translation_validating`。条件竞争不能吞掉真实仓储异常，同代停止拒绝后须锁外幂等收口，重复消息不重复写终态事件。

The backend uses a centralized API error response shape around `ApiError`, while some legacy/specialized routers still raise `HTTPException` directly.

Evidence:

- `app/core/errors.py`
- `app/api/errors.py`
- `app/api/dependencies.py`
- `app/main.py`
- `app/domains/document_jobs/service.py`
- `app/domains/document_jobs/router.py`
- `app/domains/files/service.py`
- `app/domains/jobs/workflow.py`
- `tests/test_internal_user_management.py`
- `tests/test_fastapi_jobs_backend.py`

## Public API Error Shape

`app/api/errors.py` registers FastAPI exception handlers in `register_api_error_handlers(app)`. `app/main.py` calls that during `create_app()`.

The current error response contains:

- `detail`
- `error_code`
- `request_id`
- `trace_id`
- nested `error.code`, `error.message`, `error.status_code`, `error.request_id`, `error.trace_id`

`trace_id` is set by the HTTP middleware in `app/main.py` from `X-Trace-Id` or a generated UUID hex value.

## Application Errors

Use `ApiError` from `app/core/errors.py` for service/business failures that should become stable API responses. It carries:

- HTTP status code
- stable `ApiErrorCode`
- user-facing message

Examples:

- `DocumentJobService.get_job()` raises `ApiError(404, "not_found", ...)`.
- `DocumentJobService.list_jobs()` raises `invalid_request` for illegal filters and sort values.
- `FileUploadService.create_upload_authorization()` raises `service_unavailable` when S3 storage is selected without a bucket.
- `app/api/dependencies.py` raises `unauthorized`, `invalid_token`, `role_forbidden`, and `auth_unconfigured` for auth failures.

When introducing a new stable API error code, add it to the `ApiErrorCode` literal in `app/core/errors.py` and ensure tests assert it where the behavior is externally visible.

## HTTPException And Existing Helpers

Current dominant convention for new application code is `ApiError`, but `HTTPException` still exists in the codebase:

- `app/api/errors.py` wraps `HTTPException` into the unified error shape.
- Helper functions such as `not_found_http_exception()`, `bad_request_http_exception()`, and `artifact_download_http_exception()` map lower-level exceptions.
- Some existing routers, such as parts of `app/domains/term_rules/proposals_router.py` and `app/domains/config_workbench/router.py`, still raise `HTTPException` directly.

当前未建立此约定：the repository has not fully eliminated direct `HTTPException`. Prefer `ApiError` for new domain/service behavior and use direct `HTTPException` only when matching an existing local router helper or FastAPI boundary pattern.

## Workflow And Conversion Errors

Workflow policy errors are centralized in `app/domains/jobs/workflow.py`:

- `JobWorkflowViolation` represents illegal job state/variant transitions.
- `app/api/errors.py` maps it to HTTP 409 with `error_code="job_state_conflict"`.

Conversion failures use `ConversionFailure` from `app/conversion/contracts.py`, mapped to HTTP 503 with `error_code="conversion_failed"`.

Resource snapshot failures use `JobResourceSnapshotError`, mapped through its own status code and `error_code="resource_snapshot_error"`.

Do not duplicate workflow state checks in routers when the rule already belongs in `workflow.py` or the owning service. Existing `JobStageService` applies transitions from `app/domains/jobs/workflow.py` instead of hand-building status patches in each stage branch.

## Scenario: DocumentIR Translation Provider Failures

### 1. Scope / Trigger

- Trigger: changing `app/domains/translation/document_ir_translator.py`, `app/domains/translation/provider.py`, `app/domains/translation/audit.py`, or document job `ir_converting` / `translating` / `translation_validating` behavior.
- DocumentIR translation is a provider boundary: raw DocumentIR text is transformed into provider JSON, provider JSON is parsed back into replacements, and failures must become job diagnostics instead of partial translated documents.

### 2. Signatures

- `DocumentIRTranslationService(provider, max_items_per_request=300, max_chars_per_request=8000)`
- `TranslationProvider.translate(TranslationProviderRequest) -> TranslationProviderResult`
- `TranslationCallAuditRecorder.record_success(...)` and `record_failure(...)` may be called once per provider batch.

### 3. Contracts

- Each provider request contains only one bounded batch of `TranslationTextItem` values.
- Returned `items` must match the request item IDs in the same order.
- One `ai_call_log` document file is written per provider call; if full-text debug is enabled, one `ai_debug_archive` is written per provider call.
- `DocumentJobExecutionService` keeps compatibility fields `ai_call_log_file_id` / `debug_archive_file_id` and also records plural `ai_call_log_file_ids` / `debug_archive_file_ids` in translation metadata and stage payloads.

### 4. Validation & Error Matrix

- Provider raises, returns invalid JSON, missing `items`, empty item text, or mismatched item IDs -> raise `DocumentIRTranslationError`.
- `DocumentJobExecutionService._classify_worker_failure()` 将 Provider/单批次翻译失败映射为 `error_code="translation_failed"`、`failed_stage="translating"`；全量合并/回填失败定位 `translation_validating`，missing/extra ID 保留 `translation_fan_in_mismatch`，文件/存储错误保留 `oss_failed`。历史 `ir_converting` 诊断仍可读取；阶段与恢复的唯一合同见 [DocumentJob 模式与阶段合同](./document-job-mode-contract.md#8-执行阶段与恢复合同con-102)。
- Already written call logs are still recorded as job events, but translated text replacements are applied only after all batches validate.

### 5. Good/Base/Bad Cases

- Good: 1500+ text fragments are split into multiple provider calls; all batches validate; DocumentIR is saved once with complete replacements.
- Base: a small document fits one batch and still produces the historical single `ai_call_log`.
- Bad: sending the full document as one provider request can produce malformed provider JSON and user-visible `translation_failed`.

### 6. Tests Required

- Unit: `tests.test_document_ir_translation` must assert batch sizes, request order, trace `batch_id`, and final replacement order.
- API/domain: `tests.test_fastapi_jobs_backend` must cover successful batched audit artifacts, provider failure audit logs, and retry after translation failure.

### 7. Wrong vs Correct

#### Wrong

```python
request = TranslationProviderRequest(items=tuple(all_document_items), ...)
provider.translate(request)
```

#### Correct

```python
for batch_items in self._split_provider_batches(all_document_items):
    prepared = self.build_provider_request(..., items=batch_items)
    result = provider.translate(prepared.request)
    validated = self.validator.validate(prepared.source_items, prepared.encoded_batch, result)
    replacements.update(validated.replacements)
# 所有批次成功后才回填；不能在循环内 apply。
```

## Validation Boundaries

Request schema validation is handled by FastAPI/Pydantic. `RequestValidationError` is mapped to HTTP 422 and `error_code="validation_error"`.

Business validation belongs in services and should raise `ApiError`. Examples include:

- File upload metadata/content validation in `app/domains/files/service.py` and `app/domains/files/validation.py`.
- Document job visibility, state, retry, cancel, delete, and download validation in `app/domains/document_jobs/service.py`.
- Auth and role checks in `app/api/dependencies.py`.

Pydantic model validators are used for record invariants. `DocumentJobRecord._validate_state()` rejects invalid status/stage combinations.

## Bulk And Partial Failure Behavior

Some bulk endpoints intentionally catch `ApiError` per item and return item-level failures instead of failing the whole request. `app/domains/document_jobs/router.py` does this for bulk retry/archive/cancel.

Only use this pattern when the API response schema explicitly represents per-item success/failure. Otherwise let `ApiError` propagate to the registered handler.

## Unexpected Exceptions

The HTTP middleware in `app/main.py` logs unexpected exceptions on the `system` logger with trace, method, path, and duration, then re-raises. Stage execution uses `JobStageService._handle_stage_failure()` to update job/stage state, append events, and log business failures.

Do not add broad silent `except Exception` blocks that hide errors. If an exception is caught, either convert it to a stable `ApiError`/workflow transition or preserve it in stage/job diagnostic state.

## DocumentJob 结果登记竞争与真实错误

- first-valid-receipt选定/完成的当前代、最终IR或receipt条件不符，是正常竞争失效：返回最新权威任务，不伪造oss_failed或成功事件。
- receipt前候选的迟到异常按本次实际阶段定位，并原子要求槽位仍空；不能重新读取另一调用的current.stage后将其流程标failed。receipt后收尾错误必须匹配选定file ID。
- 阶段helper成功CAS后若事件追加、翻译计划或资源准备失败，由该owner持本次CAS返回的新快照收尾，并让调用者先检查返回状态再继续Provider、claim或文件副作用。不能只依赖外层尚未更新的旧快照，也不能用无条件最新阶段绕开条件失败保护。定向证据见`test_document_job_execution_stages.py`的首次准备失败与post-transition事件故障用例；持续事件存储故障不因此获得事务/outbox保证。
- 条件失败收尾可以返回另一调用的权威新代记录。batch调用者在阶段helper返回后、claim之前，必须同时复查`job.retry_count == batch.job_retry_count == batch.generation`，再检查状态/阶段；不能把新代任务快照用于旧代Provider或审计。该局部复查不承诺消除所有外部调用期间的并发换代，既有返回后generation保护仍须保留。
- 对象写入、legacy完整性/checksum、候选descriptor冲突、到期/删除后的物化错误按uploading/oss_failed失败关闭，保留receipt/候选及审计，不换同代结果以掩盖损坏。
- 真正任务timeout仍使用document_job_timeout；取消或超时先赢时，后续结果完成不得复活终态。retry提交发现状态/代数已变继续返回既有409 conflict。
- 具体流程和局部原子持久化保证分别由document-job-mode-contract.md §8、database-guidelines.md的DocumentJob结果登记章节定义；本节不复制结果状态机。

## CON-103/104 交付错误

复核批准必须满足成功任务、当前主 DOCX 和非阻断质量，并在同任务锁内比较 generation/result ID；不授予发布权限。`published` 记录在文件副作用前拒绝删除或内容变更。下载拒绝的 `ApiError` 可通过 keyword-only `reason_code` 透传到嵌套 `error.reason_code`，保留既有 HTTP、`error_code`、`detail` 和权限边界；未明确原因的错误不补空字段。下载动作与签发接口共用 metadata guard，真实存储/审计错误继续显式传播。
