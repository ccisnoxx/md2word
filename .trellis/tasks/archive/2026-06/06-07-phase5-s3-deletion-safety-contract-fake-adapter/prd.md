# Phase 5 S3 deletion safety contract fake adapter

## Goal

Add a fake S3 deletion safety contract to the existing file-retention physical delete and cleanup-run flows.

The contract must expose exact S3 target evidence and fake-delete safety metadata for expired S3 `document_files` without calling real S3 delete APIs, mutating S3 file metadata to `deleted`, or enabling S3 cleanup execution.

## Requirements

- For expired S3 `document_files`, preview and execute responses must include a structured S3 deletion contract summary:
  - bucket.
  - object key.
  - optional object version id when available from metadata.
  - fake adapter mode.
  - whether the target is exact enough for a future real delete task.
  - safety flags proving no real S3 delete occurred.
- Physical delete preview must continue to be read-only and not write audit events.
- Physical delete execute must continue to skip S3 objects without mutating their metadata.
- Cleanup-run preview/execute must carry the same S3 fake contract evidence through `physical_delete.items`.
- Existing local `local_file` and `local_object` deletion semantics must remain unchanged.
- API docs, OpenAPI snapshot, TypeScript types, and targeted tests must be updated.

## Out of Scope

- No real S3 `delete_object` call.
- No S3 client adapter that can execute deletes.
- No LocalStack or network integration.
- No batch scheduler or autonomous cleanup.
- No provider cancellation, alert delivery, parsing, translation, or Word generation.
- No quota enforcement.

## Acceptance Criteria

- [x] S3 expired files return a fake S3 contract in delete preview.
- [x] S3 expired files return the same fake contract in delete execute and remain `expired`.
- [x] Cleanup-run preview/execute responses include S3 fake contract evidence for S3 items.
- [x] Safety metadata proves `real_s3_delete_executed=false` and `fake_s3_delete_executed` reflects fake handling.
- [x] No test or implementation path calls real S3 delete.
- [x] Local deletion tests still pass.
- [x] OpenAPI/docs/frontend types are aligned.
- [x] Trellis task validates and is archived.

## Notes

- This is integration readiness only. A future real S3 deletion task must add provider-specific preview, fake/LocalStack tests, explicit confirmation, audit details, rollback policy, and separate approval before enabling any real object delete.
