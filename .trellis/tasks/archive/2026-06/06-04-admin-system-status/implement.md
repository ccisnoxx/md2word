# Admin system status implementation plan

This plan is for the implementation phase after review. Do not run `task.py start` until scope is approved.

## Checklist

1. Add health API contract
   - Add `HealthReadyResponse` and `HealthMetricsResponse` to `frontend/src/api/types.ts`.
   - Create `frontend/src/api/health.ts` with `getReady()` and `getMetrics()`.
   - Verification: `npm --prefix frontend run build` should typecheck the new API wrapper.

2. Implement readonly system status page
   - Replace the placeholder in `frontend/src/pages/SystemStatusPage.vue`.
   - Fetch ready and metrics in parallel on mount and refresh.
   - Show loading and `ApiErrorAlert` failure state.
   - Render Overview, Backend/Worker/Storage, Jobs/Queue, Resources.
   - Use local helper functions for `unknown` dependency check fields.
   - Do not add mutation buttons or any job/file/config operation calls.
   - Verification: build plus manual code inspection that the page imports only health/client/format/error helpers.

3. Add minimal `/jobs` query initialization if needed
   - Read `route.query.status` and apply it when it matches `DocumentJobStatus`.
   - Read `route.query.include_archived` and `route.query.sort` conservatively.
   - Keep existing manual filters and pagination behavior.
   - Verification: build; no backend workflow execution.

4. Final validation
   - Run `npm --prefix frontend run build`.
   - If backend files were changed unexpectedly, run the smallest related FastAPI tests; otherwise no backend tests are required.
   - Confirm the Trellis task remains planning until user approval starts implementation.

## Review Gates

- Before implementation: user reviews the scope, files, API/page changes, and acceptance criteria.
- Before finishing implementation: verify no calls were added to create/retry/cancel/archive/download/delete endpoints from `SystemStatusPage.vue`.

## Rollback

- Revert `frontend/src/api/health.ts`, health type additions, `SystemStatusPage.vue`, and any minimal `JobsPage.vue` query initialization.
- No persisted data or backend state should be affected by this task.

## Execution Notes

- Added frontend-only health API wrapper and types for `/api/v1/health/ready` and `/api/v1/health/metrics`.
- Replaced the placeholder Admin system status page with readonly readiness, backend, worker, storage, job/queue, and resource panels.
- Added minimal `/jobs` query initialization for system status links.
- Verified `SystemStatusPage.vue` does not import or call document job / file mutation APIs.

## Validation Results

- `npm --prefix frontend run build` passed.
- `python3 ./.trellis/scripts/task.py validate 06-04-admin-system-status` passed.
- Playwright CLI smoke with mocked readonly API responses passed:
  - `/system-status` rendered ready, Backend, Worker, Storage, Jobs / Queue, and Resources sections.
  - `/jobs?status=failed&sort=updated_at_desc` initialized the task list as `当前视图：失败`.
  - Final smoke run reported no console warnings or errors.
