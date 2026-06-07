# Phase 5 signed cleanup plan foundation implementation

## Classification

- Type: additive API/domain/frontend safety contract.
- Behavior change: cleanup run preview/execute responses include a signed plan; execute can verify plan fields before deletion.
- Risk: plan validation must run before physical delete and preserve old-client compatibility.

## Checklist

1. Planning
   - [x] Fill `prd.md`, `design.md`, `implement.md`.
   - [x] Validate task.
   - [x] Start task.

2. Backend
   - [x] Add signed cleanup plan model and builder/verifier.
   - [x] Persist plan inside cleanup run history.
   - [x] Extend schemas and router response mapping.
   - [x] Validate optional plan fields before cleanup execute.
   - [x] Record failed history for plan validation failures.

3. Frontend and docs
   - [x] Update frontend TS contracts.
   - [x] Pass plan id/signature into execute.
   - [x] Display plan summary in cleanup run result/history.
   - [x] Update API docs and OpenAPI snapshot.

4. Verification
   - [x] Add/update targeted backend tests.
   - [x] Run targeted cleanup run tests.
   - [x] Run metadata adapter contract if model persistence changes need coverage.
   - [x] Run OpenAPI export/test.
   - [x] Run frontend build.
   - [x] Run browser smoke if frontend changed.
   - [x] Run Trellis validate.
   - [x] Run `git diff --check`.

## Verification Commands

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_cleanup_run_preview_and_execute_records_history tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_cleanup_run_history_is_admin_only_and_not_destructive tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_cleanup_run_signed_plan_blocks_tampering
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_database_job_repository.PersistenceAdapterTests.test_metadata_repository_contract_matches_file_backend
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/export_openapi.py
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_openapi_export
npm --prefix frontend run build
python3 ./.trellis/scripts/task.py validate 06-07-phase5-signed-cleanup-plan-foundation
git diff --check
```

## Non-execution Reminder

Do not run pdf-mineru parsing, MinerU recovery query/download, real translation providers, Word generation, real alert delivery, real provider cancellation, cleanup scheduler loops, real S3 deletion, or autonomous destructive cleanup.

## Verification Results

- PASS: `tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_cleanup_run_preview_and_execute_records_history`
- PASS: `tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_cleanup_run_signed_plan_blocks_tampering`
- PASS: `tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_cleanup_run_history_is_admin_only_and_not_destructive`
- PASS: `tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_retention_cleanup_run_execute_reuses_physical_delete_contract_and_audits`
- PASS: `tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_retention_cleanup_run_guards_hash_limits_and_registry_contract`
- PASS: `tests.test_database_job_repository.PersistenceAdapterTests.test_metadata_repository_contract_matches_file_backend`
- PASS: `scripts/ops/export_openapi.py`; `docs/api/openapi.json` changed, schema count became 235.
- PASS: `tests.test_openapi_export`, 3 tests.
- PASS: `npm --prefix frontend run build`; Vite emitted existing Rollup pure-comment warnings and chunk-size advisory only.
- PASS: Browser smoke for `/system-status/file-retention`; protected route redirected to login with 0 console errors.
- PASS: `python3 ./.trellis/scripts/task.py validate 06-07-phase5-signed-cleanup-plan-foundation`.
- PASS: `git diff --check`.
