# Admin system status design

## Current State

The parent roadmap already introduced `SystemStatusPage` into the protected app shell:

- `frontend/src/router/index.ts` registers `/system-status` with `meta.roles = ["admin"]`.
- `frontend/src/layouts/AppLayout.vue` shows the "系统状态" navigation item only for Admin.
- `frontend/src/pages/SystemStatusPage.vue` currently renders a placeholder card and does not call backend health APIs.

Backend health endpoints already expose the target data:

- `GET /api/v1/health/ready` returns `HealthReadyResponse` with `dependency_checks`.
- `GET /api/v1/health/metrics` returns `HealthMetricsResponse` with metadata store, artifact storage, worker mode, stage dispatcher, job counts, stage message counts, resource counts, and audit event count.

## Scope

This child task is frontend-first and read-only:

- Add typed frontend health API wrappers.
- Replace the placeholder system status page with real readonly status panels.
- Add URL query initialization to the jobs list only if needed to make status links from the system page work.

No backend route is planned. No conversion, retry, cancel, archive, download, upload, deletion, or config mutation API should be invoked from this page.

## Files

Expected implementation files:

- `frontend/src/api/types.ts`
  - Add `HealthReadyResponse` and `HealthMetricsResponse` frontend contracts matching `app/api/v1/routers/health_schemas.py`.
- `frontend/src/api/health.ts`
  - New small wrapper around `/api/v1/health/ready` and `/api/v1/health/metrics`.
- `frontend/src/pages/SystemStatusPage.vue`
  - Replace placeholder content with readonly panels and refresh/error state.
- `frontend/src/pages/JobsPage.vue`
  - Minimal query-read support for `status`, `include_archived`, and `sort` if system status links depend on those query params.

Backend/spec files are read-only unless implementation reveals a contract gap:

- `app/api/v1/routers/health.py`
- `app/api/v1/routers/health_schemas.py`
- `app/services/health_service.py`
- `docs/api/health.md`

## Data Flow

```
SystemStatusPage mounted / refresh
  -> frontend health API wrappers
  -> GET /api/v1/health/ready
  -> GET /api/v1/health/metrics
  -> derived view model in SystemStatusPage
  -> readonly Element Plus panels
```

The frontend owns presentation labels and coarse state derivation. The backend remains the source of truth for readiness and metrics values.

## UI Model

Use four sections:

- Overview
  - readiness status, app name, generated time, refresh action.
  - derive status from `dependency_checks.deployment_init_ready`, blockers, warnings, and request failure.
- Backend / Worker / Storage
  - metadata store, artifact storage, worker mode, stage dispatcher, stage message store.
  - artifact writable and disk free from readiness dependency checks.
- Jobs / Queue
  - job status counts from metrics.
  - stage message counts from metrics plus stale / needs-attention fields from readiness checks.
  - links to failed and active job filters.
- Resources
  - default template, term rule set, translation term set, translation profile.
  - metrics currently reports template / term rule set / translation profile defaults; readiness may also report defaults.
  - translation term set may be absent in current health contract, so show "not reported" instead of inventing a value.

## API / Page Changes

API changes:

- No backend API addition in the planned implementation.
- Frontend adds a new `healthApi` wrapper only.

Page changes:

- `/system-status` becomes a real Admin-only readonly status page instead of an entry placeholder.
- `/jobs` may begin honoring route query parameters for status links:
  - `status=failed`
  - `status=running`
  - optionally `include_archived=true`
  - optionally `sort=created_at_desc`

## Tradeoffs

- Do not add `GET /api/v1/system/status` now. The existing endpoints already contain the required fields, and keeping aggregation in the page avoids backend contract churn.
- Do not create shared status visualization components yet. This is currently one page; extraction is only warranted if later Ops pages reuse the same panels.
- Do not mask missing health fields. Unknown or absent fields should render as `not reported` so Admin can distinguish "healthy false" from "not in contract".

## Risks

- `dependency_checks` is typed as `Record<string, unknown>` in the frontend because the backend schema intentionally allows mixed values. Keep extraction helpers local and defensive.
- JobsPage query syncing should stay minimal. Avoid converting the whole page into a bidirectional URL state manager in this task.
