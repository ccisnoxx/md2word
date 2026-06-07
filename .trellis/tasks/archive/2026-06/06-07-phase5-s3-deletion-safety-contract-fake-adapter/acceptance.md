# Phase 5 S3 deletion safety contract fake adapter acceptance

## Decision

Accepted: S3 deletion readiness now has an explicit fake adapter safety contract.

Not accepted: real S3 deletion remains deferred.

## Evidence

- S3 physical delete preview returns `s3_delete_contract`.
- S3 physical delete execute returns `s3_delete_contract`, keeps outcome `skipped_unsupported_storage`, and leaves metadata status as `expired`.
- Cleanup-run preview/execute carries the same S3 fake contract evidence through `physical_delete.items`.
- Cleanup-run preview hash includes the fake contract payload.
- Frontend File Retention result tables expose concise S3 fake contract labels.
- API docs and OpenAPI snapshot include the new field.

## Verification

- PASS: 3 targeted FastAPI tests.
- PASS: OpenAPI export, `schema_count=239`.
- PASS: `tests.test_openapi_export`.
- PASS: `npm --prefix frontend run build`.
- PASS: Trellis validation.
- PASS: `git diff --check`.

## Safety Statement

No real S3 delete was added or executed. The fake contract reports `real_s3_delete_executed=false` and `requires_future_real_adapter=true`.
