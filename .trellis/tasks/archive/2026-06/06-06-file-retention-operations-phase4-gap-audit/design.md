# File retention operations Phase 4 gap audit design

## Scope

This is a planning-only gap audit. It does not change backend code, frontend code, API contracts, persistence schemas, runtime settings, tests, or production behavior.

The output is a reviewable decision document for the first Phase 4 Operations and Retention implementation slice.

## Inputs Reviewed

| Input | Relevant conclusion |
| --- | --- |
| `AGENTS.md` | Source changes require tight scope, verification by evidence, no destructive operations without explicit approval, and no claims without observed evidence. |
| `.trellis/workflow.md` | Complex planning must produce `prd.md`, `design.md`, and `implement.md`; review comes before `task.py start`. |
| Product roadmap `prd.md` / `design.md` / `implement.md` | Phase 4 is Operations and Retention: file management, retention policy, physical deletion, cleanup plan, storage statistics, audit query, worker/queue monitoring, alerting, recovery/cancel improvements. |
| Product roadmap `acceptance.md` | Retention, audit export, worker monitoring, and alerting are deferred to Phase 4 unless directly needed by Phase 3 evidence. |
| Phase 1 closeout | Workbench, job files/results, task actions, config, proposals, and read-only system status are closed; physical deletion and file library remain out of scope. |
| Phase 2 closeout | Configuration governance is closed; retention/audit/ops tasks are not Phase 2 blockers. |
| Phase 3 closeout | Result QA is closed; `ai_debug_archive` is retention-limited, so Phase 4 must preserve honest unavailable states. |
| `file-retention-management` | Metadata-only foundation exists: `GET /api/v1/files/retention/plan`, `POST /api/v1/files/retention/mark-expired`, and `/system-status/file-retention`. It explicitly excludes physical deletion, policy CRUD, scheduler, quota, full file library, and download controls. |
| `audit-log-viewer` | Admin-only audit query and current-page frontend CSV export exist. No backend-generated export, audit retention purge, or mutation. |
| `ops-dashboard` | Admin-only read-only dashboard exists. It intentionally avoids worker controls, recovery, cleanup, retry, deletion, and alert configuration. |

## Current Capability Matrix

| Area | Current evidence | Gap |
| --- | --- | --- |
| Retention plan | `DocumentFileRetentionPlanner.build_plan()` uses `document_files.expires_at`; API returns `deletion_supported=false` and `action_mode=dry_run`. | No preview contract for actual deletion effects, no immutable plan token/hash, no explicit candidate selection contract. |
| Metadata expiry | `mark-expired` changes eligible `uploaded` candidates to `expired` and records `file.retention_mark_expired`. | It still leaves binaries in local/object/S3 storage by design. |
| Physical deletion | No `DELETE /api/v1/files/{file_id}` and no document_files object deletion service. Legacy `/api/v1/jobs/{job_id}/cleanup-local-files` removes old job work dirs only. | Missing storage-delete port, status transition to `deleted`, per-file audit, idempotency rules, object-missing handling, confirmation, and tests. |
| Retention policy | `oss_file_retention_days` is a runtime setting used during file creation and planning. | No policy model, CRUD, per-file-type policy, publish/audit model, or policy history. |
| Scheduled cleanup | No background retention runner for `document_files`. | Needs safe manual delete semantics first; otherwise scheduler would automate an unreviewed destructive action. |
| Storage quota | Health reports `artifact_disk_free_bytes` and writability. | No used bytes by storage provider/file type/status, no quota config, no cleanup recommendations, no enforcement. |
| File search/library | Task detail has `/document-jobs/{job_id}/files`; Files API has single-file get and retention plan candidates. | No cross-task paginated file list, filters, search, sorting, tenant-safe Admin file library, or per-file action view. |
| Audit query/export | `/api/v1/audit-events` filters/sorts/paginates; UI exports current loaded page CSV. | No backend full filtered export, no async export job, no audit payload/details model, no retention/export policy. |
| System status/ops | `SystemStatusPage` and `OpsDashboardPage` read health/metrics and job samples. | No alert config, worker process control, queue operations, or destructive ops controls. |

## Candidate Decision Matrix

| Candidate first slice | Readiness | Risk | Decision |
| --- | --- | --- | --- |
| Physical deletion | Highest implementation leverage because expired-candidate planning and metadata expiry already exist. | High irreversible risk unless dry-run, confirmation, audit, and idempotency are explicit. | Recommended, but only as a constrained manual safety-contract slice. |
| Retention policy CRUD | Useful after deletion exists. | Changing policy before delete safety can silently widen candidate blast radius. | Defer. |
| Scheduled cleanup | Operationally useful after manual deletion is safe. | Automates irreversible deletion without a proven manual primitive. | Defer. |
| Storage quota | Useful for planning and recommendations. | Enforcement depends on deletion semantics; reporting-only would not close lifecycle gap. | Defer after manual deletion or run as a later read-only companion. |
| File search | Useful for file library UX. | Larger UI/API surface; does not establish destructive-operation safety. | Defer until deletion candidates need richer discovery. |
| Audit export | Existing viewer already provides query and current-page export. | Full export is less urgent than creating auditable events for the high-risk operation itself. | Defer. |

## Recommended Phase 4 First Slice

Recommended next implementation task: `file-retention-physical-delete-safety-contract`.

The first Phase 4 slice should implement manual physical deletion for already-expired `document_files`, with dry-run and confirmation gates. It should not introduce a scheduler, policy editor, full file library, storage quota enforcement, or audit export.

The key reason is dependency order: policy CRUD, scheduled cleanup, quota enforcement, and file-library actions all depend on a trustworthy deletion primitive. Without that primitive, those features either stay read-only or automate an unsafe operation.

## Proposed Safety Contract

### Eligibility

- Admin-only.
- Only `document_files` records are in scope.
- Only records with `status=expired` and `expires_at <= now` are executable deletion candidates.
- `uploaded` records must go through the existing `mark-expired` step first.
- `pending_upload`, non-expired `uploaded`, and already `deleted` records are not executable.
- No document job rows, document job events, audit events, proposal records, or file metadata rows are removed.
- `object_key` remains in metadata for traceability even after binary deletion.

### Dry-run and confirmation

- A dry-run preview must be generated before execution.
- Execution must receive exact `file_ids`, not a broad "delete all" instruction.
- Execution should require a confirmation phrase such as `DELETE EXPIRED FILES`.
- Execution should require a human reason.
- Execution should cap the batch size, for example 50 IDs, matching existing bulk-operation scale.
- Execution should re-read all file records immediately before deletion and skip candidates that no longer match eligibility.

### Deletion behavior

- Local deletion must resolve paths through the existing path guard, not string-concatenate paths in the router.
- S3 deletion should call object storage through a narrow service method, not expose raw boto3 calls in the router.
- Missing object should be idempotent: record a skipped or already-missing outcome and allow metadata transition only if the record is still expired and the requested object identity matches.
- Metadata should move to `deleted` only after storage deletion succeeds or the object is proven missing under an idempotent policy.
- The response must return per-file outcomes: `deleted`, `skipped`, `failed`, current status, storage provider, and reason.

### Audit

- Record one summary event such as `file.retention_physical_delete`.
- Record enough per-file detail to reconstruct file IDs, counts, skip/failure counts, reason, actor, trace ID, and confirmation mode.
- If the current `AuditEvent.reason` field is too narrow for per-file detail, use compact reason text for the first slice and document the need for a future structured `details` field.
- Do not store file bytes, prompt/response text, tokens, full local absolute paths, or secrets in audit events.

### UI

- Start from `/system-status/file-retention`.
- Add explicit copy that physical deletion is irreversible and only affects expired binaries, not task/event/metadata records.
- Keep the existing metadata-only `mark expired` action separate from physical deletion.
- Disable execution until the user selects candidates, enters a reason, and confirms the phrase.
- Display dry-run and post-run outcomes before any navigation.

## Backend Shape For The Next Task

This is a proposed shape for review, not an implementation in this task.

| Area | Suggested change |
| --- | --- |
| Files schemas | Add request/response schemas for physical-delete preview and execution. |
| Files service | Add a narrow deletion method that validates `DocumentFileRecord` eligibility and delegates binary deletion by storage provider. |
| Files router | Add Admin-only retention delete endpoints under static `/files/retention/...` routes before `/{file_id}`. |
| Repository | Reuse `update_document_file()` for `status=deleted`; avoid deleting metadata rows. |
| Storage | For local storage, delete only paths resolved by existing `resolve_local_object_path()`. For S3, call `delete_object` through a service method. |
| Audit | Record summary audit after successful execution attempt with trace ID and reason. |
| Docs/tests | Update `docs/api/files.md`, OpenAPI snapshot if API changes, `tests/test_artifact_retention.py`, and targeted `tests/test_fastapi_jobs_backend.py` cases. |

## Non-goals For The First Slice

- No policy CRUD.
- No scheduled cleanup worker.
- No quota enforcement.
- No cross-task file library.
- No deletion of legacy `job_files` artifacts through `ArtifactRetentionPlanner`.
- No calls to `/api/v1/jobs/{job_id}/cleanup-local-files`.
- No MinerU recovery, retry, cancel, parsing, translation, or Word generation.
- No audit export beyond existing viewer behavior.

## Residual Risks

- Current repository ports use full-list scans. That is acceptable for a first manual batch but not for a large file library or scheduler.
- Current `AuditEvent` has only `reason`, not structured details. Per-file deletion evidence may need a follow-up model extension.
- S3 deletion behavior depends on deployment credentials and provider semantics; tests should use fake clients and avoid real network calls.
- Existing `ai_debug_archive` evidence can expire, so deletion copy must explain QA evidence availability consequences.

## Review Gate

Stop here for review. Do not run `task.py start` until the user approves the first-slice decision and implementation boundary.
