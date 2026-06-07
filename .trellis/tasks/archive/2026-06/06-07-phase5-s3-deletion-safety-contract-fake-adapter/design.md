# Phase 5 S3 deletion safety contract fake adapter design

## Boundary

This slice extends the current "S3 is unsupported" skip result into an explicit fake deletion safety contract. It does not execute real S3 deletion and does not make S3 cleanup executable.

Excluded:

- `boto3.delete_object`.
- S3 batch delete.
- LocalStack/network tests.
- autonomous cleanup scheduler.
- quota enforcement.
- provider cancellation.
- alert delivery.
- pdf-mineru parsing, translation, or Word generation.

## Current State

- `FileUploadService._retention_delete_eligibility()` returns `skipped_unsupported_storage` for all non-local providers.
- S3 items currently carry bucket/object identity only through existing `bucket`/`object_key` metadata, but API item responses do not expose a specific S3 safety contract.
- Cleanup-run preview/execute reuses the same physical-delete report, so adding evidence to `FileRetentionDeleteItem` propagates to cleanup-run responses.

## Contract

Add `s3_delete_contract` to each `FileRetentionDeleteItem`.

For non-S3 items:

```json
null
```

For S3 items:

```json
{
  "contract_version": "s3-delete-fake-v1",
  "adapter_mode": "fake",
  "bucket": "test-bucket",
  "object_key": "document-jobs/.../s3.docx",
  "version_id": null,
  "target_exact": true,
  "missing_target_fields": [],
  "expected_outcome": "fake_skipped",
  "safety": {
    "real_s3_delete_executed": false,
    "fake_s3_delete_executed": true,
    "metadata_mutated": false,
    "audit_events_written": false,
    "requires_future_real_adapter": true
  }
}
```

`target_exact=false` when bucket or object key is blank. In that case, include `missing_target_fields`.

Object version id source:

- Use `record.metadata["s3_version_id"]` when it is a non-blank string.
- Otherwise `null`.
- Do not read or return credentials.

## Outcome Policy

Keep the existing `skipped_unsupported_storage` outcome for S3 items to preserve client compatibility. The new `s3_delete_contract.expected_outcome=fake_skipped` gives machine-readable fake adapter evidence without changing current skip behavior.

Execute behavior:

- Return S3 item as `skipped_unsupported_storage`.
- Do not call `_s3_client()`.
- Do not call repository `update_document_file()` for the S3 item.
- Do not mark S3 metadata as `deleted`.

Preview hash:

- Cleanup-run preview hash currently includes `object_key`, outcome, provider, and status. Add the fake contract to the hash payload so a future contract change invalidates stale cleanup-run previews safely.

## Files

- `app/domains/files/service.py`
  - Extend `FileRetentionDeleteItem`.
  - Add `FileRetentionS3DeleteContract`.
  - Build fake S3 contract for S3 records.
- `app/domains/files/schemas.py`
  - Add response schema for the fake contract and attach to delete item response.
- `app/domains/files/cleanup_execution.py`
  - Include the S3 contract in cleanup preview hash payload.
- `app/domains/files/router.py`
  - Map new field through existing response builder if required.
- `frontend/src/api/types.ts`
  - Add TypeScript type.
- `frontend/src/pages/FileRetentionPage.vue`
  - Display concise S3 contract evidence for physical delete and cleanup-run result rows.
- `docs/api/files.md`
  - Document fake contract and safety flags.
- `docs/api/openapi.json`
  - Refresh snapshot.
- `tests/test_fastapi_jobs_backend.py`
  - Update S3 skip tests and cleanup-run S3 test assertions.

## Compatibility

- Additive JSON field only.
- Existing outcomes remain unchanged.
- Existing local deletion semantics remain unchanged.
- Existing clients can ignore `s3_delete_contract`.

## Verification

Run targeted tests:

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_retention_physical_delete_skips_s3_without_mutating_metadata \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_retention_cleanup_run_execute_reuses_physical_delete_contract_and_audits \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_cleanup_run_signed_plan_blocks_tampering
```

Then run:

```bash
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/export_openapi.py
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_openapi_export
npm --prefix frontend run build
python3 ./.trellis/scripts/task.py validate 06-07-phase5-s3-deletion-safety-contract-fake-adapter
git diff --check
```
