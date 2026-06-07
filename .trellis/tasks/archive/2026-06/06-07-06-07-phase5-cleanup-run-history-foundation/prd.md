# Phase 5 cleanup run history foundation

## Goal

Persist cleanup run preview/execute outcomes as durable run history so later signed cleanup plans, locks, and scheduler dry-runs have a stable audit-ready foundation.

## Requirements

- Add durable cleanup run history records for manual cleanup-run preview and execute.
- Existing cleanup run preview must create a history record with stable `run_id`.
- Existing cleanup run execute must update or create a run history record with execution outcome.
- History records must retain:
  - `run_id`, status, action mode, preview hash, requested file IDs, max files;
  - aggregate totals and safety flags;
  - compact reason when execute is requested;
  - created/updated/executed timestamps.
- Add Admin-only list/detail APIs for cleanup run history.
- Add frontend read-only history and detail display on the File Retention page.
- Do not store object bodies, local paths, secrets, or signed URLs in history.
- Do not introduce scheduler, distributed lock, signed cleanup plan enforcement, real S3 delete, or autonomous destructive behavior.
- Preserve current physical-delete safety contract and confirmation phrase behavior.

## Acceptance Criteria

- [ ] Preview creates a durable cleanup run history record and returns the same `run_id`.
- [ ] Execute with matching preview hash updates the run record to executed and preserves safety metadata.
- [ ] Execute without a known preview can still record a failed/no-preview history outcome without bypassing current validation.
- [ ] Admin can list and read cleanup run history.
- [ ] Operator/non-admin cannot list/read cleanup run history.
- [ ] Frontend can display recent cleanup run history without adding any scheduler or new destructive control.
- [ ] Targeted backend tests, OpenAPI export/test, frontend build, browser smoke, Trellis validate, and `git diff --check` pass.

## Notes

- This is a foundation slice only. Signed cleanup plans, distributed locks, scheduler dry-runs, autonomous cleanup, real S3 deletion, and real provider calls remain out of scope.
