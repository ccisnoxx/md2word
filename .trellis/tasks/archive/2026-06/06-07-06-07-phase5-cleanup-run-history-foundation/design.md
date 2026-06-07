# Phase 5 cleanup run history foundation design

## Current State

- `FileRetentionCleanupRunService.preview()` returns an in-memory report with a generated `run_id` and `preview_hash`.
- `FileRetentionCleanupRunService.execute()` recomputes current preview from exact `file_ids`, validates `preview_hash`, then reuses existing physical-delete execution.
- Router writes compact audit only for execute.
- No durable run history exists, so later automation/signed-plan work cannot replay run state.

## Backend Design

Add a new domain module:

```text
app/domains/files/cleanup_history.py
```

It will define:

- `FileRetentionCleanupRunHistoryRecord`
- `FileRetentionCleanupRunHistoryRepositoryProtocol`
- `FileRetentionCleanupRunHistoryService`

Record fields:

- `run_id`
- `status`: `previewed | executed | failed`
- `action_mode`
- `preview_hash`
- `requested_file_ids`
- `max_files`
- `reason`
- `totals`
- `safety`
- `created_at`
- `updated_at`
- `executed_at`

The record intentionally excludes object keys and local paths. `requested_file_ids` are retained because exact target replay and later signed plans need stable target identity.

Repository adapters:

- file backend: `var/config/file_retention_cleanup_runs.json`
- sqlite backend: `file_retention_cleanup_runs`
- mysql backend: `file_retention_cleanup_runs`

Runtime wiring:

- Add `file_retention_cleanup_run_history_repository` and service-like helper through router.
- Preview calls `record_preview(report)`.
- Execute uses client-provided `run_id` when available, validates `preview_hash` through existing service, then records executed outcome.

API additions:

```text
GET /api/v1/files/retention/cleanup-runs/history
GET /api/v1/files/retention/cleanup-runs/history/{run_id}
```

Existing response extension:

- Add `history_recorded: bool` to `FileRetentionCleanupRunSafetyResponse`.

Existing execute request extension:

- Add optional `run_id` to `FileRetentionCleanupRunExecuteRequest`.

Compatibility:

- Existing clients can execute without `run_id`; backend still creates/updates a history record with returned report run ID.
- Existing preview/execute safety contract remains unchanged.

## Frontend Design

Extend existing File Retention page:

- Load cleanup run history on page refresh.
- Show a read-only history table near the cleanup run result section.
- When a cleanup preview returns `run_id`, execute request includes that `run_id`.
- Detail display shows status, preview hash, totals, requested file count, safety flags, and reason.

No scheduler controls, no auto-run controls, and no new delete behavior are added.

## Rollback

- Remove cleanup history domain/repositories/schema/routes/frontend/docs/tests/OpenAPI changes.
- Existing cleanup preview/execute can return to stateless behavior because physical-delete contract remains unchanged.
