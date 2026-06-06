# File retention policy CRUD governance

## Goal

Implement the next Phase 4 Operations and Retention slice: Admin-only retention policy CRUD governance for `document_files`.

This task started as planning-only, was reviewed by the user, then explicitly approved for `task.py start` and implementation. The implementation must preserve the physical-delete safety contract and must not run parsing, translation, Word generation, scheduled cleanup, or object deletion flows.

## Requirements

- Policy governance
  - Add persistent retention policy records for `document_files`.
  - Support `global` and `file_type` scopes.
  - Support `draft`, `published`, and `disabled` lifecycle states.
  - Support list, detail, create draft, update draft, publish, set default, disable, and impact preview.
  - Preserve policy history; no hard delete of policy records.
  - Enforce one default published policy per scope through service-level default switching.
- Expiration semantics
  - Existing `oss_file_retention_days` remains the fallback when no matching default published policy exists.
  - Published file-type policy takes precedence over published global policy.
  - Policy resolution affects only new file registration and upload authorization.
  - Existing `document_files.expires_at` must not be backfilled by this task.
  - Explicit `expires_at` passed by callers remains authoritative.
- Safety and audit
  - All policy APIs are Admin-only.
  - Publish, set-default, and disable require a non-empty human reason.
  - Policy writes create compact audit events.
  - Impact preview is dry-run only and does not write audit by default.
  - Policy preview must not mark files expired or select files for deletion.
- UI and docs
  - Extend `/system-status/file-retention` with a policy governance section.
  - Keep policy controls visually separate from physical delete controls.
  - Update Files API docs and OpenAPI snapshot.

## Non-goals

- No physical deletion execution beyond existing tests of the safety contract.
- No scheduled cleanup or retention runner.
- No quota enforcement.
- No file library/search.
- No backend audit export.
- No structured audit details migration.
- No historical expiration backfill.
- No real S3 deletion.
- No pdf-mineru parsing, real translation provider calls, or Word generation main-flow execution.

## Acceptance Criteria

- [x] `task.py start` moved the task to `in_progress` after user approval.
- [x] Backend policy domain, repository port, and file/sqlite/mysql adapters are implemented.
- [x] Runtime wiring injects policy resolution into `FileUploadService`.
- [x] Admin-only policy routes support list/detail/create/update/publish/set-default/disable/impact-preview.
- [x] Policy write routes emit audit events; impact preview remains read-only.
- [x] New file upload authorization uses effective policy while preserving settings fallback.
- [x] Historical `document_files.expires_at` remains unchanged by policy operations.
- [x] Frontend policy governance UI is added under `/system-status/file-retention`.
- [x] Files API documentation and OpenAPI snapshot are updated.
- [x] Targeted backend policy tests pass.
- [x] Existing retention safety tests pass.
- [x] Frontend build passes.
- [x] OpenAPI check passes.
- [x] `task.py validate 06-06-file-retention-policy-crud-governance` passes.
- [x] `git diff --check` passes.
- [x] Task is finished, archived, and committed.

## Notes

- User requested planning first on 2026-06-06, then explicitly requested implementation and commit.
- This implementation intentionally does not widen physical deletion behavior. Policy changes affect future `expires_at` assignment only.
