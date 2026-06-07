# Phase 5 cleanup scheduler dry-run manual runner implementation

## Classification

- Type: additive Admin-only API + history record.
- Behavior change: new dry-run endpoint only; no changes to cleanup execute behavior.
- Risk: must keep lock release reliable and avoid any delete/metadata mutation side effects.

## Checklist

1. Planning
   - [x] Fill `prd.md`, `design.md`, `implement.md`.
   - [x] Validate task.
   - [x] Start task.

2. Backend
   - [x] Extend cleanup history model/service for scheduler dry-run records.
   - [x] Add scheduler dry-run request/response schemas.
   - [x] Add Admin-only route using cleanup lock + readonly runner.
   - [x] Ensure lock release in success and report errors.
   - [x] Keep physical delete preview/execute untouched.

3. Frontend/docs
   - [x] Update frontend TS types for history dry_run status/action.
   - [x] Update API docs/manifest/OpenAPI.

4. Verification
   - [x] Add targeted FastAPI tests.
   - [x] Run targeted backend tests.
   - [x] Run OpenAPI export/test.
   - [x] Run frontend build.
   - [x] Run Trellis validate.
   - [x] Run `git diff --check`.

## Verification Commands

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_cleanup_scheduler_dry_run_manual_runner_records_history_and_releases_lock tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_cleanup_scheduler_dry_run_manual_runner_rejects_active_lock
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/export_openapi.py
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_openapi_export
npm --prefix frontend run build
python3 ./.trellis/scripts/task.py validate 06-07-phase5-cleanup-scheduler-dry-run-manual-runner
git diff --check
```

## Non-execution Reminder

Do not run pdf-mineru parsing, MinerU recovery query/download, real translation providers, Word generation, real alert delivery, real provider cancellation, cleanup scheduler loops, real S3 deletion, physical cleanup execution, or autonomous destructive cleanup.

## Implementation Summary

- Added `POST /api/v1/files/retention/cleanup-runs/scheduler-dry-run`.
- The endpoint is Admin-only, acquires `file_retention_cleanup` lock, runs the readonly cleanup runner, releases the lock, and records durable `status=dry_run` history.
- Active lock conflicts return `409 conflict` before report generation and history persistence.
- Scheduler dry-run history stores `readonly_report`, lock evidence, safe candidate file IDs, totals, preview hash, and safety flags.
- The slice does not create a signed cleanup plan and does not authorize deletion.
- Frontend API contracts now include scheduler dry-run request/response and `dry_run` cleanup history status.
- API docs and OpenAPI snapshot were updated.

## Verification Results

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_cleanup_scheduler_dry_run_manual_runner_records_history_and_releases_lock tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_cleanup_scheduler_dry_run_manual_runner_rejects_active_lock
# OK, 2 tests

/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/export_openapi.py
# ok: True, changed: True, path_count: 123, schema_count: 238

/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_openapi_export
# OK, 3 tests

npm --prefix frontend run build
# OK; existing Rollup large chunk warning remains.

/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_retention_readonly_cleanup_runner_reports_without_mutation tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_retention_cleanup_run_preview_is_admin_only_and_readonly tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_retention_cleanup_run_execute_reuses_physical_delete_contract_and_audits tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_cleanup_run_preview_and_execute_records_history tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_cleanup_run_signed_plan_blocks_tampering tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_cleanup_run_history_is_admin_only_and_not_destructive
# OK, 6 tests

/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_database_job_repository.PersistenceAdapterTests.test_cleanup_lock_service_enforces_fencing_and_expiry tests.test_database_job_repository.PersistenceAdapterTests.test_metadata_repository_contract_matches_file_backend
# OK, 2 tests

python3 ./.trellis/scripts/task.py validate 06-07-phase5-cleanup-scheduler-dry-run-manual-runner
# OK

git diff --check
# OK
```
