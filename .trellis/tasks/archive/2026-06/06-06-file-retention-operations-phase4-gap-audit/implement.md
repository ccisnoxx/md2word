# File retention operations Phase 4 gap audit implementation plan

## Status

Planning closeout complete. This task was not started with `task.py start`.

No production code has been changed. No pdf-mineru parsing, real translation provider call, Word generation, retry, recovery, cleanup, or physical deletion has been run.

The user approved moving to the next task, `file-retention-physical-delete-safety-contract`, on 2026-06-06.

## Completed In This Planning Pass

- Created Trellis planning task `file-retention-operations-phase4-gap-audit`.
- Confirmed `task.py current --source` showed no active task before creation.
- Read roadmap artifacts and Phase 1/2/3 closeout records.
- Read `file-retention-management`, `audit-log-viewer`, and `ops-dashboard` archived task evidence.
- Read current backend/frontend code and targeted tests for files, retention, storage, audit, health/system status, job file listing, and legacy ops cleanup.
- Compared current evidence against Phase 4 candidate capabilities.
- Recommended the first Phase 4 implementation slice.

## Phase 4 First-slice Recommendation

Start with physical deletion, but only as a constrained safety-contract implementation:

- Admin-only.
- Manual execution only.
- Dry-run-first.
- Only `status=expired` and `expires_at <= now`.
- Explicit selected `file_ids`.
- Required reason.
- Required irreversible confirmation phrase.
- Per-file outcomes.
- Summary audit event.
- Metadata rows retained and moved to `deleted`.
- Task rows, job events, audit events, proposals, and `object_key` retained.
- No scheduler, policy CRUD, quota enforcement, full file search, legacy cleanup, or audit export in the same slice.

## Why The Other Candidates Should Not Be First

| Candidate | Reason to defer |
| --- | --- |
| Retention policy CRUD | It can expand candidate scope before deletion safety is proven. |
| Scheduled cleanup | It automates a destructive operation that does not yet have a reviewed manual primitive. |
| Storage quota | Current health already exposes free disk bytes; enforcement depends on safe deletion semantics. |
| File search | It is a larger file-library UX/API surface and does not close the lifecycle execution gap. |
| Audit export | Existing audit viewer already supports query and current-page export; high-risk delete audit events should exist before full export becomes more valuable. |

## Proposed Next Task

Create a separate implementation task after review:

`file-retention-physical-delete-safety-contract`

Suggested scope:

- Add retention physical-delete preview and execution contracts under `/api/v1/files/retention/...`.
- Keep existing `mark-expired` metadata action separate.
- Implement binary deletion through a narrow files service method.
- Preserve metadata rows and mark deleted records as `status=deleted`.
- Add targeted backend tests for dry-run, Admin-only auth, confirmation, refusal of non-expired/uploaded records, local object deletion, object-missing idempotency, audit recording, and preservation of job/event/metadata records.
- Add frontend controls on `/system-status/file-retention` only after backend contract is stable.

## Verification Plan For This Planning Task

After review-ready docs are written:

1. Run `python3 ./.trellis/scripts/task.py validate 06-06-file-retention-operations-phase4-gap-audit`.
2. Run `git diff --check`.
3. Run `git status --short` and confirm only planning artifacts changed.

Do not run backend tests, frontend build, browser smoke, pdf-mineru parsing, real translation provider calls, Word generation, retry, recovery, cleanup, or physical deletion in this planning task unless the user explicitly changes scope.

## Review Questions

- Confirm whether the recommended first slice should be `file-retention-physical-delete-safety-contract`.
- Confirm whether deletion should require `status=expired` as a hard prerequisite, instead of allowing direct deletion of `uploaded` expired candidates.
- Confirm whether S3 deletion should be included in the first slice or initially blocked with a clear unsupported-provider response.
- Confirm whether the existing `AuditEvent.reason` field is acceptable for first-slice compact deletion audit, or whether structured audit `details` must be added first.

## Review Gate

Stop here. Do not run `task.py start` until the user approves this PRD/design/implementation plan.
