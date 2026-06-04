# Document job bulk APIs Design

## Current State

`app/domains/document_jobs/router.py` 已提供单任务创建、查询、事件、文件、下载、重试、取消和归档接口。`DocumentJobService.retry_job()`、`cancel_job()`、`archive_job()` 已集中处理状态检查、权限检查、任务记录更新和事件写入。audit event 目前由 router 在单任务 service 调用成功后写入。

`frontend/src/pages/JobsPage.vue` 已有批量重试和批量归档按钮，但实现方式是前端 `Promise.allSettled()` 逐个调用 `documentJobsApi.retry()` / `archive()`。当前没有批量取消 UI。

## Scope

本任务只新增批量 API contract 和现有列表页最小适配：

- 后端新增三个静态路由：
  - `POST /api/v1/document-jobs/bulk-retry`
  - `POST /api/v1/document-jobs/bulk-archive`
  - `POST /api/v1/document-jobs/bulk-cancel`
- 前端新增对应 API wrapper 和 TypeScript 类型。
- `JobsPage` 将现有批量重试、批量归档切换到后端 bulk API，并继续显示成功/失败数量。
- 不新增页面，不扩展任务详情，不做批量取消按钮。

## Files

- Backend:
  - `app/domains/document_jobs/schemas.py`
  - `app/domains/document_jobs/router.py`
- Frontend:
  - `frontend/src/api/types.ts`
  - `frontend/src/api/documentJobs.ts`
  - `frontend/src/pages/JobsPage.vue`
- Tests / docs:
  - `tests/test_fastapi_jobs_backend.py`
  - `docs/api/document-jobs.md`
  - `docs/api/openapi.json`

## API Contract

### Request

Each bulk request uses `job_ids: list[str]` with a small upper bound, proposed as 50.

`bulk-retry` also accepts the existing retry options:

- `reason`
- `use_latest_term_assets`
- `term_rule_set_id`
- `term_rule_set_version`
- `translation_term_set_id`
- `translation_term_version`

`bulk-archive` and `bulk-cancel` only need `job_ids`.

### Response

All three endpoints return a common response shape:

- `action`: `retry` / `archive` / `cancel`
- `total`
- `succeeded`
- `failed`
- `items`

Each item includes:

- `job_id`
- `ok`
- `status_code`
- `error_code`
- `detail`
- `job`

Successful items set `ok=true`, `status_code=200`, `job` to the latest `DocumentJobResponse`, and error fields to null. Failed items set `ok=false`, include the single-task error status and code, and omit `job`.

### Error Handling

Batch-level request validation fails fast with `400 invalid_request` for:

- empty `job_ids`
- more than 50 `job_ids`
- duplicate `job_ids`

Per-item failures are collected and returned in `items` with `200 OK` for the batch response. This keeps partial success observable and avoids rolling back already-successful state changes in a repository layer that has no transaction manager.

### Route Ordering

Static bulk routes must be declared before `/{job_id}` routes in `app/domains/document_jobs/router.py`, otherwise FastAPI route matching can treat bulk path segments as `job_id`.

## Behavior

- Bulk retry calls existing `DocumentJobService.retry_job()` per job id.
- Bulk archive calls existing `DocumentJobService.archive_job()` per job id.
- Bulk cancel calls existing `DocumentJobService.cancel_job()` per job id.
- Router records the same audit action after each successful item.
- `trace_id` is passed through each per-item service call and audit record.
- No new service touches pdf-mineru, translation, Word generation, file storage deletion, or document file metadata shape.

## Frontend Impact

No new page or visible workflow.

`JobsPage` existing bulk retry and bulk archive handlers will call the new bulk API and compute success/failure counts from the response. Row-level retry/archive/cancel remain unchanged. Bulk cancel API is exposed in `documentJobsApi` for contract completeness, but not added to UI in this task.

## Tradeoffs

- Batch response uses `200 OK` even when some items fail. This is intentional because the request itself was valid and some state transitions may already have been applied.
- No all-or-nothing transaction is introduced. Current file/sqlite/mysql repository ports do not expose a cross-job transaction boundary, and the product need is lightweight workbench batching.
- Reusing single-task service methods may enqueue retried jobs in a real deployment when a Worker backend is configured. Tests for this task should use a runtime without eager Worker execution to avoid rerunning the main flow.

## Verification Strategy

- Add targeted FastAPI tests in `tests/test_fastapi_jobs_backend.py` for:
  - bulk archive success and partial failure
  - bulk cancel success and partial failure
  - bulk retry success and partial failure without eager Worker execution
  - batch-level validation for empty/duplicate/too many ids
  - audit events for successful items
- Regenerate OpenAPI after intentional API change.
- If frontend wrappers/types change, run the existing frontend typecheck/build command from `frontend/package.json` if available.
