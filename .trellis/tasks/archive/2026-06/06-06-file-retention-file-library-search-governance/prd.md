# File retention file library search governance

## Goal

Add an Admin-only, read-only `document_files` library search slice so operators can locate files by stable metadata before using existing retention, storage usage, and delete-preview workflows.

## Requirements

- Add a backend search endpoint for `document_files` metadata.
- Endpoint must be Admin-only and read-only.
- Endpoint must support pagination, sorting, exact filters, and free-text search across stable safe metadata.
- Endpoint must not expose `object_key`, `bucket`, checksums, etags, raw metadata payloads, local absolute paths, file bytes, prompts, credentials, or signed URLs.
- Endpoint must not add delete, download, upload, mark-expired, physical delete, scheduler, quota enforcement, or bulk action behavior.
- Response rows must include enough safe fields to identify a file and feed existing selected-file workflows: `file_id`, `job_id`, `file_type`, `storage_provider`, `original_filename`, `mime_type`, `size_bytes`, `status`, `expires_at`, `created_by`, `created_at`, `updated_at`, and derived expiry/deletion-candidate booleans.
- Frontend `/system-status/file-retention` must add a read-only file library search section.
- Frontend search section must not expose object locators or provide direct delete/download controls.
- Existing retention plan, policy, storage usage, and physical-delete safety flows must remain unchanged.
- OpenAPI and TypeScript contracts must be updated.

## Acceptance Criteria

- [x] Task exists.
- [x] `prd.md`, `design.md`, and `implement.md` define the read-only search governance boundary.
- [x] `task.py validate` passes before start.
- [x] `task.py start` is run.
- [x] Backend search service/endpoint is implemented with safe row projection.
- [x] Endpoint supports Admin success, Operator rejection, pagination, sorting, filters, and free-text search.
- [x] Tests prove no object locator or sensitive fields are returned.
- [x] Frontend search UI is implemented under `/system-status/file-retention`.
- [x] OpenAPI snapshot is regenerated and OpenAPI tests pass.
- [x] Frontend build passes.
- [x] `task.py validate` passes after implementation.
- [x] `git diff --check` passes.

## Notes

- This task is the next Phase 4 slice after physical delete safety, policy CRUD, storage usage readiness, scheduled cleanup readonly runner, and audit export governance.
- This task does not run pdf-mineru parsing, real translation providers, Word generation, physical deletion, S3 deletion, quota enforcement, or scheduler loops.
- Observed implementation verification passed on 2026-06-06.
