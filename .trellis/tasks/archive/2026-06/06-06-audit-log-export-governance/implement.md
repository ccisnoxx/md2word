# Audit log export governance implementation

## Checklist

1. Backend query/export service
   - Add export result dataclass and bounded export method to `app/domains/audit/query.py`.
   - Add CSV encoding helper in the audit domain.
   - Keep filtering/sorting shared with the list path.
   - Status: done.

2. Backend API contract
   - Add export schemas to `app/domains/audit/schemas.py`.
   - Add `GET /api/v1/audit-events/export` to `app/domains/audit/router.py`.
   - Record `audit_events.export` only after CSV generation.
   - Status: done.

3. Frontend integration
   - Add response types to `frontend/src/api/types.ts`.
   - Add API wrapper method in `frontend/src/api/auditEvents.ts`.
   - Add "导出筛选结果" action to `frontend/src/pages/AuditLogPage.vue`.
   - Status: done.

4. Tests and docs
   - Add targeted tests in `tests/test_fastapi_jobs_backend.py`.
   - Regenerate `docs/api/openapi.json`.
   - Run OpenAPI snapshot tests if the export script changes the snapshot.
   - Status: done.

5. Trellis closeout
   - Record observed verification.
   - Run `task.py validate`.
   - Run `git diff --check`.
   - Status: done.

## Validation Commands

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_audit_events_export_api_is_admin_only_bounded_and_audited tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_audit_events_export_api_rejects_operator
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/export_openapi.py
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_openapi_export
npm --prefix frontend run build
python3 ./.trellis/scripts/task.py validate 06-06-audit-log-export-governance
git diff --check
```

Observed:

- `python3 ./.trellis/scripts/task.py validate 06-06-audit-log-export-governance` passed before `task.py start`.
- `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_audit_events_export_api_is_admin_only_bounded_and_audited tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_audit_events_export_api_rejects_operator` passed.
- `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_audit_events_api_filters_sorts_and_paginates_for_admin tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_audit_events_api_rejects_operator tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_audit_events_export_api_is_admin_only_bounded_and_audited tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_audit_events_export_api_rejects_operator` passed.
- `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_retention_readonly_cleanup_runner_reports_without_mutation tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_storage_usage_is_admin_only_readonly_and_reports_reclaim_estimates tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_retention_plan_is_admin_only_and_reports_dry_run_candidates tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_retention_physical_delete_preview_is_admin_only_and_does_not_mutate tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_audit_events_api_filters_sorts_and_paginates_for_admin tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_audit_events_api_rejects_operator tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_audit_events_export_api_is_admin_only_bounded_and_audited tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_audit_events_export_api_rejects_operator` passed.
- `/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/export_openapi.py` passed and updated `docs/api/openapi.json`.
- `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_openapi_export` passed.
- `npm --prefix frontend run build` passed twice with existing Rollup chunk/annotation warnings.
- `python3 ./.trellis/scripts/task.py validate 06-06-audit-log-export-governance` passed after implementation.
- `git diff --check` passed.

## Non-Execution Reminder

Do not run pdf-mineru parsing, real translation providers, Word generation, physical deletion, S3 deletion, quota enforcement, or scheduler loops.

## Rollback

- Remove the export route, schemas, CSV helper, frontend action, tests, and OpenAPI snapshot changes.
- Existing `GET /api/v1/audit-events` remains unaffected.
