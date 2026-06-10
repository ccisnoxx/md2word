# Document Job Workbench Closure - Design

## Status

Proposed. This child task is still in Trellis planning. Do not start implementation or run the PDF-MinerU parse / translation / Word generation workflow until this design and `implement.md` are reviewed and the task is explicitly moved to execution.

## Evidence Read

- `AGENTS.md`
- `.trellis/workflow.md`
- `.trellis/tasks/06-09-md2word-product-maturity-roadmap/roadmap.md`
- `.trellis/tasks/06-09-md2word-product-maturity-roadmap/task-breakdown.md`
- `.trellis/tasks/06-09-document-job-workbench-closure/prd.md`
- Backend guidelines under `.trellis/spec/backend/` and cross-layer guides under `.trellis/spec/guides/`
- Existing backend code:
  - `app/domains/document_jobs/models.py`
  - `app/domains/document_jobs/schemas.py`
  - `app/domains/document_jobs/router.py`
  - `app/domains/document_jobs/service.py`
  - `app/domains/document_jobs/repository.py`
  - `app/infrastructure/persistence/file/document_jobs.py`
  - `app/infrastructure/persistence/sqlite/document_jobs.py`
  - `app/infrastructure/persistence/mysql/document_jobs.py`
  - `app/infrastructure/persistence/sqlite/schema.py`
  - `app/infrastructure/persistence/mysql/schema.py`
- Existing frontend code:
  - `frontend/src/router/index.ts`
  - `frontend/src/layouts/AppLayout.vue`
  - `frontend/src/api/types.ts`
  - `frontend/src/api/documentJobs.ts`
  - `frontend/src/pages/JobsPage.vue`
  - `frontend/src/pages/JobDetailPage.vue`
  - `frontend/src/pages/TranslationResultQaPage.vue`
  - `frontend/src/pages/SettingsHomePage.vue`
  - `frontend/src/pages/TemplateListPage.vue`
  - `frontend/src/pages/TemplateDetailPage.vue`
  - `frontend/src/components/JobActions.vue`
  - `frontend/src/components/JobTable.vue`
  - `frontend/src/utils/format.ts`
- Current API docs: `docs/api/document-jobs.md`

## Current State

The active product API is `/api/v1/document-jobs`, implemented under `app/domains/document_jobs/`. The older `/api/v1/jobs` domain remains in the repository but is not the workbench target for this child task.

Already implemented in backend:

- `GET /api/v1/document-jobs` supports `status`, `translation_qa_status`, `q`, `sort`, `include_archived`, `created_from`, and `created_to`.
- Single-job `retry`, `cancel`, `archive`, files, events, translation QA, and download-url endpoints exist.
- Bulk `retry`, `archive`, and `cancel` endpoints exist and return per-item results.
- `archive` only patches `archived_at` / `archived_by` and writes an event + audit record; it does not delete files.

Current gaps:

- `DocumentJobResponse` has no `available_actions`, so frontend duplicates backend state rules through `can*DocumentJob()` helpers.
- There is no `unarchive`.
- There is no `clone/rerun as new job`; existing `retry` mutates the original failed job and must stay semantically separate.
- Frontend lacks global breadcrumb; several pages use local return buttons or only top navigation.
- `/jobs` does not expose all already-supported filters/actions ergonomically: date range, failed/running quick views, batch cancel, and disabled reasons.
- `/jobs/:jobId` is a long stacked page rather than a clear overview/files/events/diagnostics/context workbench.

## Scope

In scope:

- Workbench UX improvements for `/jobs` and `/jobs/:jobId`.
- Global breadcrumb / hierarchy navigation covering job list, job detail, translation QA detail, settings pages, and system-status child pages touched by navigation.
- `DocumentJobResponse.available_actions`, with each action returning `enabled` and `disabled_reason`.
- `unarchive` metadata operation.
- `clone/rerun as new job` operation that creates a new job and leaves the source job unchanged.
- Event and audit records for user-visible actions: `retry`, `clone`, `cancel`, `archive`, `unarchive`, and download authorization where already present.
- Tests and docs for the new contracts.

Out of scope:

- Real task deletion.
- Task-scoped file deletion.
- Batch upload.
- Standalone job configuration preset page or preset entity.
- Online translation editing.
- Any implementation that reruns the live PDF-MinerU / translation / Word generation main workflow during planning or validation.

## Backend Contract

### `DocumentJobResponse.available_actions`

Add a computed response field. It is not persisted.

```json
{
  "available_actions": {
    "download": {
      "enabled": true,
      "disabled_reason": null
    },
    "retry": {
      "enabled": false,
      "disabled_reason": "只有 failed 且未归档的可重试任务允许重试。"
    },
    "cancel": {
      "enabled": false,
      "disabled_reason": "只有 pending、queued、running 且未归档任务允许取消。"
    },
    "archive": {
      "enabled": false,
      "disabled_reason": "只有 succeeded、failed、canceled 且未归档任务允许归档。"
    },
    "unarchive": {
      "enabled": false,
      "disabled_reason": "任务未归档。"
    },
    "clone": {
      "enabled": true,
      "disabled_reason": null
    }
  }
}
```

Action IDs:

- `download`: authorize result or selected task file download through existing download-url endpoint.
- `retry`: retry a failed source job in place. Must never create a new job.
- `cancel`: cancel a pending/queued/running job.
- `archive`: hide a terminal job from default list views.
- `unarchive`: restore an archived job to default list views.
- `clone`: create a new job from the source job input and selected config strategy. UI text should say `重新发起为新任务` / `Rerun as new job`, not `重试`.

Rules:

- The response should include all known action keys for every job, so frontend can render stable controls and tooltips.
- `disabled_reason` is `null` when enabled and a user-facing Chinese reason when disabled.
- Existing service validation remains the source of truth. `available_actions` is a projection for display and primary UI state, not a replacement for endpoint-side checks.
- Frontend may keep lightweight fallback helpers only for old responses or defensive rendering.

Initial availability rules:

| Action | Enabled when | Disabled examples |
|---|---|---|
| `download` | `status=succeeded` and `result_file_id` is present | job not succeeded, result missing |
| `retry` | not archived, `status=failed`, retry count below limit, failure is retryable | archived, non-failed, max retries, `document_job_invalid_input` |
| `cancel` | not archived, `status in pending/queued/running` | terminal or archived |
| `archive` | not archived, `status in succeeded/failed/canceled` | running/non-terminal or already archived |
| `unarchive` | `archived_at != null` | not archived |
| `clone` | visible source job, source PDF metadata exists, source PDF is uploaded and not expired | source file missing, source file not uploaded, source file expired |

### `POST /api/v1/document-jobs/{job_id}/unarchive`

Purpose: restore an archived job to normal workbench list visibility. It does not restart, retry, mutate files, or delete anything.

Response:

```json
{
  "job_id": "docjob_xxx",
  "restored_at": "2026-06-09T00:00:00Z",
  "job": {
    "...": "DocumentJobResponse"
  }
}
```

Behavior:

- If the job is not archived, return the current job idempotently with a fresh `restored_at` response timestamp, or reject with `409`. Implementation should choose one behavior and test it; preferred behavior is idempotent success because archive already behaves idempotently for already-archived jobs.
- Patch `archived_at=None`, `archived_by=None`, and `updated_at=now`.
- Append `job_unarchived` document-job event.
- Write `document_job.unarchive` audit event.
- Keep files and events unchanged.

### `POST /api/v1/document-jobs/{job_id}/clone`

Purpose: create a new document job from the source job input. The source job remains unchanged. This endpoint is the backend contract for `clone/rerun as new job`.

Request:

```json
{
  "reason": "operator requested rerun after config publish",
  "config_strategy": "keep_source_snapshot",
  "document_language": "auto",
  "template_version_id": null,
  "term_rule_set_id": null,
  "term_rule_set_version": null,
  "translation_term_set_id": null,
  "translation_term_version": null,
  "translation_profile_id": null,
  "translation_profile_version": null,
  "debug_full_text": false
}
```

`config_strategy` values:

- `keep_source_snapshot` (default): copy reusable config from the source job request snapshot when possible. This is the safest default for reproducing a result as a new job.
- `use_current_defaults`: reuse the source file and mode but resolve current default business resources.
- `select_published_versions`: use explicit published resource versions from request fields. Existing admin-only resource selection rules apply.

Response:

```json
{
  "source_job_id": "docjob_source",
  "job_id": "docjob_new",
  "status": "pending",
  "stage": "uploaded",
  "progress": 0,
  "job": {
    "...": "DocumentJobResponse"
  }
}
```

Behavior:

- Creates a new `DocumentJobRecord` with a new `id`, current user as `created_by`, same tenant/company, same `source_file_id`, same `mode` by default, and requested/resolved config.
- Does not mutate the source job.
- Does not mutate the source file's existing `job_id` if it is already bound to the source job. Existing file listing already treats `file.id == job.source_file_id` as belonging to a job, so a cloned job can display and download its source PDF without stealing file ownership.
- Sets `source_job_id` on the new job.
- Adds clone metadata to `request_snapshot.clone`, including source job id, config strategy, normalized reason, and a non-sensitive copy of source request snapshot or equivalent config summary.
- Appends `job_cloned` event to the new job and a `job_cloned_from` or equivalent event to the source job only if that does not create noisy event history. Preferred minimum: new job event plus audit event with `target_id=new_job_id` and details containing `source_job_id`.
- Writes `document_job.clone` audit event.
- Enqueues the new job through the existing task queue path, same as create. Planning and unit tests must use fake/eager paths only; do not call the real PDF-MinerU / translation / Word pipeline.

## Data Model

Add optional persisted fields to `DocumentJobRecord`:

```python
source_job_id: str | None = None
```

Add matching API fields:

```python
DocumentJobResponse.source_job_id: str | None = None
DocumentJobAvailableActionResponse
DocumentJobAvailableActionsResponse or dict[str, DocumentJobAvailableActionResponse]
DocumentJobUnarchiveResponse
DocumentJobCloneRequest
DocumentJobCloneResponse
```

Extend event type literals:

- `job_unarchived`
- `job_cloned`

Do not persist `available_actions`; it is computed from the job, current user visibility, source file metadata, settings, and service rules.

## Persistence And Migration

Current file, sqlite, and MySQL document-job repositories persist the whole `DocumentJobRecord` payload as JSON. SQLite/MySQL `document_jobs` tables have `job_id`, `payload`, `created_at`, and `updated_at`; no column-level schema change is required for `source_job_id`.

Migration plan:

- Add `source_job_id: None` default to the Pydantic model so old `job.json` and DB payload rows continue to validate.
- No backfill is required. Existing jobs have `source_job_id=null`.
- File backend writes the new field automatically through `model_dump`.
- SQLite/MySQL adapters continue to store the payload JSON; no DDL migration is needed.
- Update `docs/api/openapi.json` after implementation because response/request schemas change.

## Frontend Design

### Global Breadcrumb

Add a layout-level breadcrumb directly under the sticky header in `AppLayout.vue`.

Recommended implementation:

- Add route meta or a small route-name resolver in `frontend/src/router/index.ts` / a nearby helper.
- Render breadcrumb items in a reusable component, for example `frontend/src/components/AppBreadcrumb.vue`.
- Dynamic labels can use route params for this task; no extra backend calls are needed.

Coverage:

- `/jobs`: `任务工作台`
- `/jobs/:jobId`: `任务工作台 > 任务详情 > {jobId}`
- `/jobs/:jobId/translation-qa`: `任务工作台 > 任务详情 > {jobId} > 翻译 QA`
- `/settings`: `配置中心`
- `/settings/templates`: `配置中心 > 模板配置`
- `/settings/templates/:templateId`: `配置中心 > 模板配置 > {templateId}`
- `/settings/term-rule-sets`: `配置中心 > 术语规则集`
- `/settings/term-rules`: `配置中心 > 术语规则检查`
- `/settings/translation-profiles`: `配置中心 > 翻译配置`
- `/settings/translation-term-sets`: `配置中心 > 翻译术语集`
- `/term-proposals`: role-aware `提案审核` / `术语建议`
- `/system-status`: `系统状态`
- `/system-status/ops-dashboard`: `系统状态 > 运维看板`
- `/system-status/audit-events`: `系统状态 > 审计日志`
- `/system-status/file-retention`: `系统状态 > 文件保留`

Generic local return buttons on job detail, QA detail, and template detail should be removed or demoted after breadcrumb is present. Contextual deep-link returns that carry proposal-specific query state can remain until the navigation/role-model follow-up.

### `/jobs`

Page changes:

- Keep single-file upload.
- Keep existing search/status/QA/sort/archived filters.
- Add date range controls wired to existing `created_from` / `created_to`.
- Add quick filters:
  - `失败任务`: `status=failed&sort=updated_at_desc`
  - `处理中`: `status=running&sort=updated_at_desc`
  - optionally `已归档`: `include_archived=true`
- Add batch cancel button beside existing batch retry/archive.
- Use `available_actions` for row buttons, disabled states, tooltips, and batch selectable filtering.
- In archived view, show an explicit non-destructive archive hint and expose per-row `unarchive` where enabled.
- Add `clone` row action text `重新发起` / `新任务`.
- Do not add batch upload or delete controls.

### `/jobs/:jobId`

Restructure the existing stacked sections into clearer tabs or segmented sections:

- `概览`: status, progress, source PDF, mode, bound resources, retry count, archive/cancel timestamps.
- `诊断`: failure stage, error code/message, latest error event, retry availability reason.
- `文件`: existing file table and task-file download.
- `事件`: event timeline plus filters for `level` and `stage` on the client side.
- `运行上下文`: request snapshot, resource snapshot, term proposal shortcuts.

Actions:

- `JobActions` should render `download`, `retry`, `cancel`, `archive`, `unarchive`, `clone`, and `refresh`.
- `retry` opens the existing retry dialog and stays failed-job/in-place semantics.
- `clone` opens a separate dialog titled `重新发起为新任务`; it must not reuse retry wording or call `retry`.
- `unarchive` confirms restore and calls the new unarchive endpoint.

### Shared Action Helpers

Replace current `canDownloadDocumentJob`, `canRetryDocumentJob`, `canArchiveDocumentJob`, and `canCancelDocumentJob` as primary gates with helpers that read `job.available_actions`.

Keep fallback behavior for old API responses:

- If `available_actions` is missing, fall back to current status-based helpers.
- If an action is disabled, expose `disabled_reason` in button tooltip or adjacent disabled reason text.

## Security And Permissions

- Preserve existing visibility rules: admin can access tenant/company jobs; operator can access own jobs.
- Existing explicit resource selection restrictions continue to apply: operator cannot select published resource versions directly; admin can.
- Clone/rerun must validate source job visibility and source file tenant/company.
- Clone/rerun must not expose full text, prompt/response bodies, secrets, or raw provider payloads in events, audit details, or request snapshot.
- Download remains tokenized through the existing download-url flow.

## API Documentation

Update:

- `docs/api/document-jobs.md`
- `docs/api/openapi.json` via the existing export script after code changes.
- Frontend TypeScript types in `frontend/src/api/types.ts`.

## Rollout And Rollback

The backend contract is additive:

- New response field `available_actions`.
- New optional model field `source_job_id`.
- New endpoints `unarchive` and `clone`.

Rollback is straightforward:

- Revert the new endpoints and frontend controls.
- Existing persisted rows with `source_job_id` remain valid if the field is ignored by older code only if Pydantic model allows extra fields. Because current models do not intentionally rely on extra fields, safest rollback is to keep the optional field in the model even if clone UI is disabled.
- `archive` and existing retry/cancel/download contracts remain unchanged.

## Testing Strategy

Backend tests in `tests/test_fastapi_jobs_backend.py`:

- `DocumentJobResponse` includes all `available_actions` keys for list and detail.
- Disabled reasons match status/archived/retry-limit/non-retryable cases.
- Single and bulk UI-facing actions still fail with endpoint-side validation even if a stale client sends a disabled action.
- `unarchive` clears archive fields, restores default list visibility, writes `job_unarchived` event, and writes `document_job.unarchive` audit event.
- `clone` creates a new job, preserves source job unchanged, sets `source_job_id`, references same `source_file_id`, records source config snapshot/equivalent request snapshot details, writes event/audit, and does not increment source retry count.
- `clone` rejects unavailable source files and unauthorized jobs.
- Operator/admin resource selection behavior matches create/retry rules.

Frontend validation:

- `npm run build` from `frontend/`.
- Manual/browser smoke after implementation:
  - `/jobs` filters and quick filters.
  - batch retry/cancel/archive buttons disable from `available_actions`.
  - archived job can unarchive.
  - failed job retry remains separate from clone.
  - clone creates a new job id and navigates to the new detail.
  - breadcrumb path works for jobs, job detail, translation QA, settings templates list/detail, and system-status child pages.

