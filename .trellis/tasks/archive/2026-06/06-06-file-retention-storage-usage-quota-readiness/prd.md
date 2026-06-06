# File retention storage usage quota readiness

## Goal

Implement the next Phase 4 Operations and Retention slice: Admin-only, read-only storage usage and quota readiness for `document_files`.

This task started as planning-only, was reviewed by the user, then explicitly approved for `task.py start` and implementation. The implementation must keep storage usage advisory and read-only.

## Requirements

- Scope
  - Add an Admin-only read-only storage usage summary for `document_files`.
  - Summarize file counts and `size_bytes` by storage provider, file type, and file status.
  - Summarize retention-related reclaim opportunity from metadata, especially expired local/local-object records that are likely eligible for the existing manual physical-delete workflow.
  - Show unsupported or blocked reclaim categories such as `s3`, non-expired files, deleted metadata rows, missing `object_key`, and non-`expired` statuses.
  - Surface current artifact storage readiness context: configured artifact storage backend, local artifact root writable state, and free disk bytes when available.
  - Keep quota status advisory only: no upload blocking, no enforcement, no automatic cleanup.
- Safety constraints
  - Admin-only API and UI.
  - Read-only by default: no metadata mutation, no object deletion, no mark-expired, no retention-policy mutation.
  - No scheduled cleanup, no background runner, no cron-like execution.
  - No physical-delete execution and no broad "delete all" action.
  - No S3 deletion.
  - No historical `expires_at` backfill.
  - No calls to pdf-mineru parsing, real translation providers, or Word generation.
  - Do not expose local absolute paths, raw `object_key` lists in summary cards, file bytes, prompts, credentials, or secrets.
- UI expectations
  - Reuse `/system-status/file-retention`.
  - Add storage usage cards and grouped tables above the existing retention candidates.
  - Label reclaim numbers as metadata-estimated, not verified deletion results.
  - Link users back to the existing manual dry-run physical-delete flow instead of executing deletion from the summary.

## Non-goals

- No quota enforcement or upload rejection.
- No scheduler, cleanup runner, or automated deletion.
- No file search/library or per-file browsing API.
- No backend audit export.
- No structured audit details migration.
- No new destructive operation.
- No full filesystem crawl or path-by-path verification in this implementation.
- No new quota environment settings in this implementation.

## Acceptance Criteria

- [x] Planning task existed and was reviewed before `task.py start`.
- [x] `task.py start` moved the task to `in_progress` after user approval.
- [x] Backend read-only storage usage service is implemented.
- [x] Admin-only `GET /api/v1/files/storage/usage` is implemented before `/{file_id}`.
- [x] API response includes totals, reclaim summary, advisory quota readiness, and groups by storage provider/file type/status.
- [x] The endpoint does not mutate metadata, write audit, mark expired, preview deletion, execute deletion, or call storage deletion.
- [x] Frontend storage usage/readiness section is implemented on `/system-status/file-retention`.
- [x] Files/health API docs and OpenAPI snapshot are updated.
- [x] Targeted storage usage API test passes.
- [x] Existing retention safety tests pass.
- [x] Existing retention policy tests pass.
- [x] Artifact retention tests pass.
- [x] Frontend build passes.
- [x] OpenAPI check passes.
- [x] `task.py validate 06-06-file-retention-storage-usage-quota-readiness` passes after implementation docs update.
- [x] `git diff --check` passes after implementation docs update.
- [x] Task is finished, archived, and committed after user request.

## Notes

- User requested this as the next Phase 4 planning slice on 2026-06-06, then approved implementation and final finish/archive/commit.
- Dependency order: physical delete safety and policy CRUD are complete, so a read-only storage readiness slice can safely prepare quota and cleanup decisions without automating irreversible work.
