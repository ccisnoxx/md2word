# Error Handling

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

- Trigger: changing `app/domains/translation/document_ir_translator.py`, `app/domains/translation/provider.py`, `app/domains/translation/audit.py`, or document job `ir_converting` behavior.
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
- `DocumentJobExecutionService._classify_worker_failure()` maps `DocumentIRTranslationError` to `error_code="translation_failed"` and `failed_stage="ir_converting"`.
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
    result = provider.translate(self._build_provider_request(..., items=batch_items))
    replacements.update(self._validate_result(batch_items, result))
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
