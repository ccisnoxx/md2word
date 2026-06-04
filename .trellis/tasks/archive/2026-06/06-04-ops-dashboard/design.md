# Ops dashboard design

## Current State

`frontend/src/pages/SystemStatusPage.vue` already gives Admin a Phase 1 read-only status page. It pulls:

- `GET /api/v1/health/ready`
- `GET /api/v1/health/metrics`

Those responses already include worker mode, stage dispatcher, stage message store, stage message counts, stale running observations, readiness blockers/warnings, metadata store, artifact storage, storage writability, resource default labels, job status counts, and audit event totals.

`frontend/src/pages/JobsPage.vue` already supports `status`, `sort`, `include_archived`, and search query parameters. `frontend/src/pages/JobDetailPage.vue` already exposes task-level retry/cancel/archive/download actions. This task must not duplicate or broaden those actions.

The backend has older `app/domains/jobs/ops_router.py` endpoints such as `recover-mineru-result` and `cleanup-local-files`, but the current workbench uses `app/domains/document_jobs`. This task does not bridge those domains or expose old jobs ops actions.

## Scope

Implement a focused frontend-only dashboard:

- New route: `/system-status/ops-dashboard`
- New page: `frontend/src/pages/OpsDashboardPage.vue`
- Link from `frontend/src/pages/SystemStatusPage.vue`, likely in the Worker or Jobs / Queue panel.
- Reuse existing API wrappers:
  - `healthApi.getReady()`
  - `healthApi.getMetrics()`
  - `documentJobsApi.list({ status: "failed", sort: "updated_at_desc", page_size: 5, include_archived: false })`
  - `documentJobsApi.list({ status: "running", sort: "updated_at_desc", page_size: 5, include_archived: false })`

No backend route, schema, persistence, worker, or lifecycle changes are planned.

## Involved Files

- `frontend/src/pages/OpsDashboardPage.vue`
  - New Admin-only dashboard page.
  - File header required by project instructions.
  - New helper functions should have concise Chinese comments.
- `frontend/src/router/index.ts`
  - Import page and register Admin route `/system-status/ops-dashboard`.
  - Update file header if modified.
- `frontend/src/pages/SystemStatusPage.vue`
  - Add a link to the new dashboard.
  - Update file header if modified.
- `frontend/src/api/types.ts`
  - No expected change; current health and document job types are enough.
- `frontend/src/api/health.ts` / `frontend/src/api/documentJobs.ts`
  - No expected change.

If implementation discovers that existing frontend types are insufficient, add only type-level frontend fields that match existing backend responses.

## API / Page Changes

### API Changes

No new backend API.

Existing read-only calls:

- `GET /api/v1/health/ready`
- `GET /api/v1/health/metrics`
- `GET /api/v1/document-jobs?status=failed&sort=updated_at_desc&page=1&page_size=5&include_archived=false`
- `GET /api/v1/document-jobs?status=running&sort=updated_at_desc&page=1&page_size=5&include_archived=false`

The page must not call:

- `POST /api/v1/document-jobs/{job_id}/retry`
- `POST /api/v1/document-jobs/{job_id}/cancel`
- `DELETE /api/v1/document-jobs/{job_id}`
- old jobs ops endpoints such as `recover-mineru-result` or `cleanup-local-files`

### Page Behavior

Top summary:

- Overall operations status: `ok`, `watch`, or `needs_attention`, derived client-side from existing health/metrics values.
- Worker mode and stage dispatcher.
- Queue pressure: pending/running/failed/replayable/stale.
- Failed/running document job counts.

Alert panel:

- Derived alerts with severity and next-step links.
- Examples:
  - Readiness blocked: link to `/system-status`.
  - Failed stage messages: suggest checking failed jobs/events; link to `/jobs?status=failed&sort=updated_at_desc`.
  - Stale running messages: show worker mode-specific guidance from current docs; link to running jobs.
  - Replayable messages: explain that pending/running stage messages may replay on restart/worker processing.

Task sample panels:

- Failed jobs, up to 5 rows.
- Running jobs, up to 5 rows.
- Rows link to `/jobs/{job.id}`.
- Footer links to filtered `/jobs` view.

Operational references:

- Link to `/system-status/audit-events`.
- Link to `/system-status/file-retention`.
- Link to `/system-status`.

## Data Flow

```text
OpsDashboardPage mounted
  -> Promise.all([
       healthApi.getReady(),
       healthApi.getMetrics(),
       documentJobsApi.list(failed sample),
       documentJobsApi.list(running sample)
     ])
  -> derive status cards and alerts in computed values
  -> render read-only guidance and navigation links
```

## Tradeoffs

- Frontend-only is the smallest sufficient implementation because health/metrics already expose the required worker and queue signals.
- The dashboard intentionally avoids direct recovery buttons. Existing job detail actions remain the controlled place for task lifecycle operations.
- The dashboard shows a small sample of jobs rather than introducing a new backend aggregate. Full queue drill-down, alert configuration, worker process control, and bulk recovery are deferred.

## Compatibility

- No persisted schema change.
- No OpenAPI contract change.
- No auth model change; route uses existing `meta.roles = ["admin"]`.
- No change to document job lifecycle operations.
- No conversion pipeline execution.

## Risks

- Health stage message counters come from the legacy stage spool, while the current frontend workbench uses `document_jobs`; this is acceptable because the runtime health service is already the source of worker/queue readiness.
- The dashboard cannot prove whether an external worker OS process is alive; it can only display configured mode, dispatcher, stage message symptoms, and next-step guidance.
- Because job samples use current paginated document job list calls, they are examples rather than a complete operational audit.

## Review Gate

Do not run `task.py start` or implement code until this design is reviewed and approved.
