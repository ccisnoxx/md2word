# Document Job Workbench Closure - Implementation Plan

## Start Gate

Do not implement until the user confirms `design.md` and this `implement.md`.

Before implementation:

- Keep task status in `planning`.
- Do not run real PDF-MinerU parsing, translation provider calls, or Word generation main workflows.
- Use backend unit/API tests with fake/eager local services only.

## Ordered Checklist

### 1. Backend Response Contract

- Add `DocumentJobAvailableActionResponse` and the `available_actions` field to `DocumentJobResponse`.
- Add action IDs: `download`, `retry`, `cancel`, `archive`, `unarchive`, `clone`.
- Implement one service-owned action availability helper so list/detail/table/UI all consume the same backend rules.
- Update router response builders to pass current user/runtime context into `_build_document_job_response`.
- Add tests proving list and detail responses include the action map and disabled reasons.

Validation after this step:

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend
```

### 2. Backend `unarchive`

- Extend `DocumentJobEventType` with `job_unarchived`.
- Add `DocumentJobUnarchiveResponse`.
- Add `DocumentJobService.unarchive_job()`.
- Add `POST /api/v1/document-jobs/{job_id}/unarchive`.
- Write document-job event and `document_job.unarchive` audit record.
- Keep files untouched.
- Add tests for:
  - archived job restored to default list.
  - event and audit written.
  - non-visible job forbidden.
  - non-archived job behavior matches the final design choice.

Validation after this step:

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend
```

### 3. Backend `clone/rerun as new job`

- Add `source_job_id: str | None = None` to `DocumentJobRecord` and `DocumentJobResponse`.
- Add `DocumentJobCloneRequest` and `DocumentJobCloneResponse`.
- Extend `DocumentJobEventType` with `job_cloned`.
- Add `DocumentJobService.clone_job()`.
- Reuse create-job resource resolution paths where possible; extract a small internal helper only if it prevents duplicating create logic.
- Do not call `_get_source_file_for_create()` directly for clone because it rejects source files already bound to a job. Instead validate:
  - source file exists.
  - source file is `source_pdf`.
  - source file status is `uploaded`.
  - source file tenant/company match.
  - source file is not expired.
- Do not mutate the source file's existing `job_id`.
- Add `POST /api/v1/document-jobs/{job_id}/clone`.
- Record source traceability:
  - new job `source_job_id`.
  - `request_snapshot.clone.source_job_id`.
  - config strategy.
  - non-sensitive source snapshot/config summary.
  - audit details with source and new job ids.
- Enqueue the new job through the same queue adapter used by create.
- Add tests for:
  - new job id created.
  - source job unchanged.
  - source retry count unchanged.
  - source file reused without rewriting its `job_id`.
  - `source_job_id` round-trips through file and database payload models.
  - clone and retry stay separate endpoints and response semantics.

Validation after this step:

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend
```

### 4. Backend Docs And OpenAPI

- Update `docs/api/document-jobs.md`.
- Regenerate `docs/api/openapi.json`.

Commands:

```bash
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/export_openapi.py
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/check_release.py
```

If `check_release.py` is too broad for the implementation turn, run the OpenAPI export plus targeted backend tests first and report the remaining release check explicitly.

### 5. Frontend Types And API Wrapper

- Add TypeScript types for:
  - action IDs and `available_actions`.
  - `source_job_id`.
  - unarchive response.
  - clone request/response.
- Add API wrapper methods:
  - `documentJobsApi.unarchive(jobId)`
  - `documentJobsApi.clone(jobId, payload)`
- Replace primary action gating with helpers that read `available_actions`.
- Keep old status-based helpers only as fallback when old API responses are missing `available_actions`.

Validation after this step:

```bash
cd frontend && npm run build
```

### 6. Global Breadcrumb

- Add route breadcrumb metadata or a resolver keyed by route name.
- Add a reusable breadcrumb component and render it in `AppLayout.vue`.
- Cover:
  - jobs list/detail/translation QA.
  - settings home and all settings child pages.
  - system status and child pages.
  - term proposals.
- Remove generic local parent-return buttons from job detail, translation QA detail, and template detail once breadcrumb covers them.
- Keep proposal-specific return buttons that preserve deep-link query state.

Validation:

```bash
cd frontend && npm run build
```

Manual smoke after implementation should confirm breadcrumb navigation on `/jobs`, `/jobs/:jobId`, `/jobs/:jobId/translation-qa`, `/settings/templates`, `/settings/templates/:templateId`, and `/system-status/file-retention`.

### 7. `/jobs` Workbench UI

- Add created date range filter wired to `created_from` / `created_to`.
- Add quick filters for failed, running, and archived views.
- Add batch cancel button using existing `bulk-cancel`.
- Update batch selectable logic to use `available_actions.retry/archive/cancel`.
- Add per-row `unarchive` and `clone` actions.
- Show disabled reasons through tooltips or disabled button hints.
- Keep single-file upload only.
- Do not add delete controls.
- Do not add batch upload controls.

Validation:

```bash
cd frontend && npm run build
```

### 8. `/jobs/:jobId` Detail UI

- Restructure content into tabs or clear segmented sections:
  - `概览`
  - `诊断`
  - `文件`
  - `事件`
  - `运行上下文`
- Add client-side event filters for `level` and `stage`.
- Extend `JobActions` to support `unarchive` and `clone`.
- Keep retry dialog unchanged in semantics.
- Add separate clone dialog:
  - title `重新发起为新任务`.
  - default `keep_source_snapshot`.
  - optional current defaults / published version selection according to role.
  - success navigates to the new job detail.
- Ensure text never suggests clone is retry.

Validation:

```bash
cd frontend && npm run build
```

### 9. Final Verification

Run the smallest checks that cover the actual changed surface:

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend
cd frontend && npm run build
```

If API docs changed:

```bash
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/export_openapi.py
```

Optional release gate if time permits:

```bash
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/check_release.py
```

Do not run scripts that create real document conversion jobs against live MinerU, live translation providers, or the Word generation main workflow.

## Review Gates

- Backend contract gate: tests prove `available_actions`, `unarchive`, and `clone` behavior before frontend depends on them.
- Frontend gate: `npm run build` passes after TypeScript contract updates.
- UX gate: breadcrumb replaces generic local returns and clone/retry wording is visibly distinct.
- Safety gate: no delete, task-scoped file deletion, batch upload, or preset page appears in code or UI.

## Rollback Points

- After step 1: revert response field and frontend helper changes; persisted data is unaffected.
- After step 2: revert unarchive endpoint/UI; archived job records remain compatible.
- After step 3: disable/revert clone endpoint/UI. Keep `source_job_id` optional field in the model if any cloned rows were created during local tests, because it is harmless and prevents older payload validation issues.
- After frontend steps: backend endpoints remain additive; revert UI files if visual or flow issues are found.

## Residual Risks To Watch

- `clone` reuses the source PDF by metadata reference. If physical file content was already removed by retention while metadata remains, clone creation may pass but execution can fail later. The implementation should disable clone when metadata is expired and let the execution path surface physical-storage failures clearly.
- Action availability can go stale between list render and click. Endpoint-side validation must remain authoritative.
- Existing `DocumentJobService` is already large. Extract only narrow helpers needed to avoid duplicating create/clone config resolution; do not introduce a broad new workflow framework in this task.

## Implementation Result - 2026-06-09

- Backend implemented `available_actions`, `unarchive`, and `clone/rerun as new job` as additive document-jobs API changes.
- Frontend implemented global breadcrumb, list/detail clone and unarchive actions, date filters, quick filters, batch cancel, detail tabs, and event filters.
- API docs and OpenAPI snapshot were refreshed.
- No real PDF-MinerU parsing, translation provider calls, or Word generation main workflow was run.

Verification run:

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_response_includes_server_action_availability tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_unarchive_restores_default_list_and_writes_audit tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_clone_creates_new_job_without_mutating_source tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_clone_rejects_expired_source_and_reports_disabled_reason tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_clone_explicit_resource_selection_requires_admin
cd frontend && npm run build
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/export_openapi.py
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/check_release.py
```
