# Phase 5 cleanup run history foundation implementation

## Classification

- Type: additive persistence + API + frontend read-only history.
- Behavior change: cleanup run preview/execute now records durable history.
- Risk: persistence surface expands across file/sqlite/mysql backends; keep record shape compact and tests targeted.

## Checklist

1. Planning
   - [x] Fill `prd.md`, `design.md`, `implement.md`.
   - [x] Validate task.
   - [x] Start task.

2. Backend domain and persistence
   - [x] Add cleanup run history record/protocol/service.
   - [x] Add file/sqlite/mysql repository adapters and schema.
   - [x] Wire repository into `PersistenceAdapters` and `AppRuntime`.
   - [x] Extend cleanup run schemas with history fields/list/detail responses.
   - [x] Record preview/execute history in router without changing physical-delete validation.
   - [x] Add Admin-only history list/detail routes.

3. Frontend
   - [x] Add TS history contracts.
   - [x] Add files API wrappers.
   - [x] Pass preview `run_id` into execute.
   - [x] Add read-only cleanup run history panel.

4. Docs and verification
   - [x] Update docs/API manifest/OpenAPI.
   - [x] Add targeted backend tests.
   - [x] Run targeted backend tests.
   - [x] Run OpenAPI export/test.
   - [x] Run frontend build.
   - [x] Run browser smoke.
   - [x] Run Trellis validate.
   - [x] Run `git diff --check`.

## Verification Commands

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_cleanup_run_preview_and_execute_records_history tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_cleanup_run_history_is_admin_only_and_not_destructive
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_database_job_repository.PersistenceAdapterTests.test_metadata_repository_contract_matches_file_backend
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/export_openapi.py
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_openapi_export
npm --prefix frontend run build
python3 ./.trellis/scripts/task.py validate 06-07-06-07-phase5-cleanup-run-history-foundation
git diff --check
```

## Verification Results

- PASS: FastAPI cleanup run history tests, 2 tests.
- PASS: file/sqlite/MySQL metadata adapter contract test.
- PASS: OpenAPI export changed `docs/api/openapi.json` and `tests.test_openapi_export`, 3 tests.
- PASS: `npm --prefix frontend run build`; Vite emitted existing chunk-size advisory and Rollup pure-comment warnings only.
- PASS: Browser smoke for `/system-status/file-retention` protected route redirected to `/login?redirect=/system-status/file-retention` with 0 console errors.
- PASS: Trellis validate.
- PASS: `git diff --check`.
- Note: an initial unittest command used the wrong class name `DatabaseJobRepositoryTests`; it failed before running tests and was immediately rerun with `PersistenceAdapterTests`.

## Non-execution Reminder

Do not run pdf-mineru parsing, MinerU recovery query/download, real translation providers, Word generation, real alert delivery, real provider cancellation, cleanup scheduler loops, real S3 deletion, or autonomous destructive cleanup.
