# Audit log viewer implementation plan

## Preconditions

- Task remains in `planning` until the scope is reviewed.
- Do not start implementation until `task.py start 06-04-audit-log-viewer` is explicitly allowed.
- Do not run MinerU parsing, translation, or Word generation flows.

## Steps

1. Backend query contract
   - Add audit schemas in `app/domains/audit/schemas.py`.
   - Add read-side filtering/pagination in `app/domains/audit/query.py`.
   - Keep repository protocol unchanged unless implementation proves impossible.

2. Backend route
   - Add `app/domains/audit/router.py`.
   - Require `require_admin_user`.
   - Include the router in `app/api/v1/router.py`.
   - Keep route read-only and side-effect free.

3. Backend tests
   - Add tests to `tests/test_fastapi_jobs_backend.py`.
   - Seed audit events through `runtime.audit_service.record(...)` or repository append.
   - Cover:
     - Admin list success.
     - Operator forbidden.
     - Filtering/sorting/pagination.

4. Frontend API
   - Add audit event types to `frontend/src/api/types.ts`.
   - Add `frontend/src/api/auditEvents.ts`.

5. Frontend page and navigation
   - Add `frontend/src/pages/AuditLogPage.vue`.
   - Add route `/system-status/audit-events` with `meta.roles = ["admin"]`.
   - Add a link from `SystemStatusPage.vue` audit metric area.
   - Keep export client-side and limited to the currently loaded result page.

6. Verification
   - Run targeted backend unittest:
     - `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend`
   - Run frontend build/type verification:
     - `npm --prefix frontend run build`
   - If full backend test module is too slow, run the narrowest named unittest methods first and report the reduced scope.

## Review gates

- Stop before implementation and present scope/API/page/acceptance summary.
- If implementation requires repository signature changes or migration/index work, stop and revise design before coding.
- If tests would trigger the PDF main flow, replace them with direct audit event seeding.

## Rollback

- Remove the new audit router include.
- Remove new frontend route/page/API wrapper.
- Remove added audit types and tests.
- No persisted data migration rollback is needed because no schema change is planned.

## Implementation result

- Added Admin-only `GET /api/v1/audit-events`.
- Added audit query service with in-memory filtering, deterministic sorting, and pagination over the existing repository contract.
- Added frontend `/system-status/audit-events` page with filters, table, and current-page CSV export.
- Linked the audit viewer from the System Status audit metric card.
- Updated OpenAPI snapshot through `scripts/ops/export_openapi.py`.

## Verification run

- `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_audit_events_api_filters_sorts_and_paginates_for_admin tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_audit_events_api_rejects_operator`
- `npm --prefix frontend run build`
- `/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/export_openapi.py --check --no-diff`
