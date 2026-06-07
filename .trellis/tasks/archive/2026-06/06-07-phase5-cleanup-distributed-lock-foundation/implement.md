# Phase 5 cleanup distributed lock foundation implementation

## Classification

- Type: additive metadata persistence + domain safety primitive.
- Behavior change: none for existing cleanup execution; new lock service is not called by scheduler or delete flows.
- Risk: persistence wiring touches file/sqlite/MySQL adapter factories and fake MySQL tests.

## Checklist

1. Planning
   - [x] Fill `prd.md`, `design.md`, `implement.md`.
   - [x] Validate task.
   - [x] Start task.

2. Domain and persistence
   - [x] Add cleanup lock model/service/protocol.
   - [x] Add file/sqlite/MySQL repositories.
   - [x] Add sqlite/MySQL schema.
   - [x] Export and wire repositories through `PersistenceAdapters` and `AppRuntime`.
   - [x] Wire test runtime.

3. Tests and docs
   - [x] Extend metadata adapter contract for lock operations.
   - [x] Add focused domain service tests for acquire/refresh/release/expiry/fencing.
   - [x] Update docs if public-facing docs need a note.

4. Verification
   - [x] Run targeted tests.
   - [x] Run Trellis validate.
   - [x] Run `git diff --check`.

## Verification Commands

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_database_job_repository.PersistenceAdapterTests.test_metadata_repository_contract_matches_file_backend tests.test_database_job_repository.PersistenceAdapterTests.test_cleanup_lock_service_enforces_fencing_and_expiry
python3 ./.trellis/scripts/task.py validate 06-07-phase5-cleanup-distributed-lock-foundation
git diff --check
```

## Non-execution Reminder

Do not run pdf-mineru parsing, MinerU recovery query/download, real translation providers, Word generation, real alert delivery, real provider cancellation, cleanup scheduler loops, real S3 deletion, physical cleanup execution, or autonomous destructive cleanup.

## Verification Results

- PASS: `tests.test_database_job_repository.PersistenceAdapterTests.test_metadata_repository_contract_matches_file_backend`
- PASS: `tests.test_database_job_repository.PersistenceAdapterTests.test_cleanup_lock_service_enforces_fencing_and_expiry`
- PASS: `tests.test_database_job_repository.PersistenceAdapterTests.test_mysql_schema_bootstrap_includes_resource_versions`
- PASS: `tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_cleanup_run_preview_and_execute_records_history`
- PASS: `python3 ./.trellis/scripts/task.py validate 06-07-phase5-cleanup-distributed-lock-foundation`
- PASS: `git diff --check`
- OpenAPI export and frontend build were not rerun because this slice added no public API routes, no response schemas, and no frontend code.
