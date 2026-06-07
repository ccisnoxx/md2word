# Phase 5 S3 deletion safety contract fake adapter implementation

## Classification

- Type: additive backend/frontend/API safety contract.
- Behavior change: S3 items still skip deletion, but responses now include structured fake S3 deletion evidence.
- Risk: cleanup-run preview hash changes for S3-including previews because the S3 fake contract is added to the hash payload. This is acceptable because old stale previews should not authorize future behavior.

## Checklist

1. Planning
   - [x] Create Trellis task.
   - [x] Fill PRD.
   - [x] Add design.
   - [x] Add implementation checklist.
   - [x] Validate task.
   - [x] Start task.

2. Backend contract
   - [x] Add fake S3 deletion contract model to file retention delete item.
   - [x] Build contract for S3 records without calling S3.
   - [x] Preserve `skipped_unsupported_storage` and metadata unchanged.
   - [x] Add contract to cleanup-run preview hash payload.
   - [x] Map schema response.

3. Frontend and docs
   - [x] Update TypeScript API types.
   - [x] Display S3 contract evidence in retention result tables.
   - [x] Update Files API docs.
   - [x] Export OpenAPI.

4. Tests and validation
   - [x] Update targeted S3 and cleanup-run tests.
   - [x] Run targeted backend tests.
   - [x] Run OpenAPI export/test.
   - [x] Run frontend build.
   - [x] Run Trellis validate.
   - [x] Run `git diff --check`.

5. Finish
   - [x] Record implementation and verification results.
   - [x] Archive task.

## Safety Guard

Do not run pdf-mineru parsing, MinerU recovery query/download, translation providers, Word generation, real Slack/email/webhook delivery, real provider cancellation, real S3 deletion, quota enforcement, cleanup scheduler loops, or autonomous destructive cleanup.

## Implementation Summary

- Added `FileRetentionS3DeleteContract` and `FileRetentionS3DeleteContractResponse`.
- Added optional `s3_delete_contract` to physical delete items.
- S3 records now return `adapter_mode=fake`, exact bucket/object key/version evidence, and safety flags:
  - `real_s3_delete_executed=false`
  - `fake_s3_delete_executed=true`
  - `metadata_mutated=false`
  - `requires_future_real_adapter=true`
- Existing S3 outcome remains `skipped_unsupported_storage`.
- S3 execute still does not mutate metadata to `deleted`.
- Cleanup-run preview hash includes the S3 fake contract payload.
- File Retention UI shows concise S3 contract evidence in physical delete and cleanup-run result tables.
- Files API docs and OpenAPI snapshot were updated.

## Verification Results

PASS:

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_retention_physical_delete_skips_s3_without_mutating_metadata \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_retention_cleanup_run_execute_reuses_physical_delete_contract_and_audits \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_cleanup_run_signed_plan_blocks_tampering
```

Result: 3 tests passed.

PASS:

```bash
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/export_openapi.py
```

Result: `changed: True`, `path_count: 123`, `schema_count: 239`.

PASS:

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_openapi_export
```

Result: 3 tests passed. Existing FastAPI status-code deprecation warnings were emitted.

PASS:

```bash
npm --prefix frontend run build
```

Result: build passed. Existing Rollup pure-comment warnings and chunk-size advisory were emitted.

PASS:

```bash
python3 ./.trellis/scripts/task.py validate 06-07-phase5-s3-deletion-safety-contract-fake-adapter
```

PASS:

```bash
git diff --check
```

Result: no whitespace errors.

## Safety Result

This slice did not call `delete_object` or `delete_objects` and did not introduce any real S3 deletion path. It also did not run pdf-mineru parsing, MinerU recovery query/download, translation providers, Word generation, real alert delivery, real provider cancellation, quota enforcement, scheduler loops, or autonomous cleanup.
