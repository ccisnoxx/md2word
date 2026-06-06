# File retention physical delete safety contract

## Goal

Implement the first Phase 4 Operations and Retention destructive file lifecycle slice: Admin-only, dry-run-first physical deletion for already-expired `document_files`.

This task establishes the safety contract for future policy CRUD, scheduled cleanup, quota, and file-library work. It must stay narrow and must not run conversion workflows.

## Requirements

- Scope
  - Add backend contracts under `/api/v1/files/retention/...` for physical-delete preview and execution.
  - Only `document_files` records are in scope.
  - Only files with `status=expired` and `expires_at <= now` are executable.
  - First implementation supports local file backends only: `local_file` and `local_object`.
  - S3 candidates must return an explicit unsupported-provider outcome and must not call real S3 deletion.
  - Existing metadata-only `mark-expired` remains separate; `uploaded` files cannot be physically deleted directly.
  - Metadata records must remain and move to `status=deleted` only after a successful or idempotently missing local object deletion.
  - `object_key`, job rows, job events, audit events, proposals, and document job rows must remain.
  - Record a compact audit event after execution using the existing `AuditEvent.reason` field.
  - Add frontend controls on `/system-status/file-retention` for dry-run preview, selected file execution, reason, confirmation phrase, and per-file outcomes.
- Safety constraints
  - Admin-only endpoints and route controls.
  - Dry-run-first UX and API.
  - Execution must receive exact `file_ids`.
  - Execution requires a non-empty human reason.
  - Execution requires confirmation phrase `DELETE EXPIRED FILES`.
  - Batch size capped at 50.
  - Execution re-reads file records immediately before deletion and skips anything no longer eligible.
  - Routers must stay thin; path deletion must go through service/path guards.
- Non-goals
  - No retention policy CRUD.
  - No scheduled cleanup worker.
  - No storage quota enforcement.
  - No cross-task file search or full file library.
  - No backend audit export.
  - No deletion of legacy `job_files` artifacts through `ArtifactRetentionPlanner`.
  - No calls to `/api/v1/jobs/{job_id}/cleanup-local-files`.
  - No MinerU recovery, retry, cancel, pdf-mineru parsing, real translation provider call, or Word generation.

## Acceptance Criteria

- [x] Admin can preview physical-delete outcomes for selected expired file IDs without mutating metadata or binaries.
- [x] Operator cannot preview or execute physical deletion.
- [x] Execution rejects missing or wrong confirmation phrase.
- [x] Execution rejects empty reason.
- [x] Execution rejects empty, duplicate, blank, or more than 50 `file_ids`.
- [x] `uploaded`, `pending_upload`, non-expired, and already `deleted` records are not physically deleted.
- [x] `expired` local/local_object files are physically removed and metadata moves to `deleted`.
- [x] Missing local objects are treated idempotently for eligible expired records and metadata moves to `deleted` with an outcome that explains the object was already missing.
- [x] S3 records are skipped with explicit unsupported-provider outcome and metadata stays unchanged.
- [x] Job rows, document job events, audit events, proposals, metadata rows, and `object_key` are preserved.
- [x] Execution records a `file.retention_physical_delete` audit event with actor, trace id, reason, and compact counts.
- [x] `/system-status/file-retention` exposes a safe manual UI: preview, selected execution, reason, confirmation phrase, and outcome table.
- [x] API docs/OpenAPI/types are updated for the new contract.
- [x] Targeted backend and frontend verification passes.
- [x] No pdf-mineru parsing, real translation provider call, Word generation, retry, recovery, legacy cleanup, scheduled cleanup, or real S3 deletion is run.

## Notes

- Keep `prd.md` focused on requirements, constraints, and acceptance criteria.
- Lightweight tasks can remain PRD-only.
- For complex tasks, add `design.md` for technical design and `implement.md` for execution planning before `task.py start`.
- User approved moving from the gap audit into implementation on 2026-06-06.
