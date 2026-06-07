# Phase 5 cleanup scheduler dry-run manual runner design

## Current State

- Readonly cleanup runner exists in `app/domains/files/scheduled_cleanup.py`.
- Cleanup run history exists and can persist compact history records.
- Cleanup lock service exists and supports acquire/refresh/release/fencing.
- Existing cleanup run preview/execute remains exact-target and manually confirmed.

## Design

### Endpoint

`POST /api/v1/files/retention/cleanup-runs/scheduler-dry-run`

Request:

- `owner_id?: str`
- `lock_ttl_seconds?: int = 60`

Response:

- `run_id`
- `generated_at`
- `action_mode=scheduler_dry_run`
- `readonly_report`
- `lock`
- `safety`

### Flow

1. Normalize owner as request owner or `manual:<user.id>`.
2. Acquire cleanup lock with metadata `{trigger=manual_scheduler_dry_run, trace_id}`.
3. Build `FileRetentionReadonlyCleanupRunner.build_report()`.
4. Save history record with:
   - `status=dry_run`
   - `action_mode=scheduler_dry_run`
   - `requested_file_ids` from readonly report candidates.
   - `preview_hash` computed from readonly report payload.
   - `readonly_report` safe payload.
   - `safety` flags proving no mutation/deletion/provider call.
5. Release lock in finally.
6. Return response.

Lock acquire conflict returns 409 and does not generate report/history.

### History Extension

Extend cleanup history action/status literals:

- status: add `dry_run`
- action_mode: add `scheduler_dry_run`
- add `readonly_report: dict[str, Any]`
- add `lock: dict[str, Any]`

No executable signed cleanup plan is created for scheduler dry-run because this runner is not a delete authorization.

### Frontend

No new operation controls in this slice. Update TS contracts only because history status/action shape changes.

### Safety

- No scheduler loop.
- No physical delete preview or execute.
- No metadata mutation.
- No audit success event for cleanup execution.
- No object path, bucket, object_key, file body, credentials, provider payload, or secret in response/history.

## Verification

- FastAPI tests cover Admin success, operator forbidden, active lock conflict, history readability, lock release, and non-destructive behavior.
- OpenAPI snapshot updated because endpoint/schema changed.
- Frontend build catches TS contract updates.
