# Phase 5 cleanup scheduler dry-run frontend controls

## Goal

Add Admin-facing frontend controls on `/system-status/file-retention` for the existing manual scheduler dry-run endpoint:

`POST /api/v1/files/retention/cleanup-runs/scheduler-dry-run`

This slice exposes the safe readonly runner result, cleanup lock evidence, safety flags, and durable history linkage without adding scheduler loops, real deletion, or external side effects.

## Requirements

- Add a clearly labeled "Scheduler Dry Run" panel to `FileRetentionPage.vue`.
- The panel must call `filesApi.runRetentionCleanupSchedulerDryRun`.
- Request defaults:
  - `owner_id` optional; UI may leave it blank to let backend use `manual:{user.id}`.
  - `lock_ttl_seconds` default 60 and remain within backend bounds.
- Show result summary:
  - `run_id`, generated time, action mode.
  - retention candidate count and reclaim estimate from `readonly_report`.
  - lock owner, fencing token, status, released flag.
  - safety flags.
- After success, refresh cleanup run history and select the new history detail.
- Do not add any execute/delete/confirmation action to this panel.
- Do not expose `object_key`, bucket, local path, file content, credentials, provider payload, or secrets.
- Preserve existing cleanup preview/execute and physical delete flows.

## Acceptance Criteria

- [ ] Admin can trigger manual scheduler dry-run from the file retention page.
- [ ] UI displays readonly report summary, lock evidence, and safety flags.
- [ ] Successful dry-run refreshes durable history and opens the new history detail.
- [ ] The panel states this is readonly and not deletion authorization.
- [ ] Existing frontend build passes.
- [ ] No backend API or OpenAPI changes are required in this slice.

## Notes

- Reuse existing Element Plus visual language and compact operations layout.
- Keep all destructive scheduler and real provider/S3/alert actions out of scope.
