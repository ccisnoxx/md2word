# Ops dashboard implementation plan

Task was approved and started with `task.py start 06-04-ops-dashboard`.

## Classification

- Type: frontend-only product feature.
- Behavior: read-only dashboard and navigation; no backend mutation.
- Public contract change: no backend API change; one Admin-only frontend route.
- Main-flow risk: low, because implementation must not trigger parsing,
  translation, Word generation, retry, recovery, cleanup, or deletion.

## Ordered Checklist

1. [x] Frontend route
   - Add `frontend/src/pages/OpsDashboardPage.vue`.
   - Register `/system-status/ops-dashboard` in `frontend/src/router/index.ts`
     with `meta: { roles: ["admin"] }`.
   - Keep existing top-level navigation unchanged.

2. [x] Dashboard data loading
   - In the new page, load readiness, metrics, failed job sample, and running
     job sample in one read-only refresh function.
   - Use existing `healthApi` and `documentJobsApi` wrappers.
   - Do not call any write/mutation API.

3. [x] Derived status and alerts
   - Derive overall status from `readiness_blockers`, `readiness_warnings`,
     `stage_spool_needs_attention`, stale running count, failed stage message
     count, failed job count, and running job count.
   - Render concise alert cards with severity, explanation, and safe links.
   - Include guidance that recovery actions must be taken from existing job
     detail/list workflows or external runbooks, not from this dashboard.

4. [x] Job sample panels
   - Show up to 5 failed jobs and up to 5 running jobs.
   - Include status/stage/progress/updated time/error summary where available.
   - Link each job to `/jobs/{job.id}`.
   - Link panel footer to filtered `/jobs` views.

5. [x] System status link
   - Add a link from `frontend/src/pages/SystemStatusPage.vue` to
     `/system-status/ops-dashboard`.
   - Keep the existing system status page behavior unchanged.

6. [x] Verification
   - Run frontend build:
     `cd frontend && npm run build`
   - If practical, start/keep a frontend dev server and browser-smoke the new
     route without submitting any job operation.
   - Do not run pdf-mineru parsing, translation, Word generation, retry, or
     recovery flows.

## Rollback Points

- If the new page introduces layout/build risk, remove the route and
  `OpsDashboardPage.vue`; existing system status remains intact.
- If document job samples create confusing semantics, keep only health/metrics
  panels and defer job drill-down.
- If any required data is missing from current health/metrics, do not add a
  backend API in this task unless the user explicitly approves a scope change.

## Definition of Done

- [x] Planning artifacts approved.
- [x] Task status moved to `in_progress` before code edits.
- [x] Code implements only the Admin-only read-only dashboard.
- [x] Minimal verification actually run and results reported.
- [x] No pdf-mineru parsing, translation, Word generation, retry, recovery,
  cleanup, or physical deletion is executed.

## Implementation Summary

- Added `frontend/src/pages/OpsDashboardPage.vue`.
- Registered Admin-only route `/system-status/ops-dashboard`.
- Added a system status page link from the Jobs / Queue panel.
- The dashboard reads only:
  - `GET /api/v1/health/ready`
  - `GET /api/v1/health/metrics`
  - `GET /api/v1/document-jobs` filtered to failed and running samples
- No backend API, persistence, worker, lifecycle, retry, recovery, cleanup, or
  deletion behavior was changed.

## Verification Results

- `cd frontend && npm run build` passed.
- Playwright smoke test passed against `http://127.0.0.1:3000/system-status/ops-dashboard` with mocked admin user, health, metrics, failed job list, and running job list.
- Browser console after smoke test reported 0 errors and 0 warnings.
- Network requests observed during the new page smoke test were only:
  - `GET /api/v1/auth/me`
  - `GET /api/v1/health/ready`
  - `GET /api/v1/health/metrics`
  - `GET /api/v1/document-jobs?...status=failed...`
  - `GET /api/v1/document-jobs?...status=running...`
- System Status link smoke test passed: clicking `运维看板` navigated to `/system-status/ops-dashboard`.
- Did not run pdf-mineru parsing, translation, Word generation, retry, recovery, cleanup, or physical deletion.
