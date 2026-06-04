# File retention management design

## Current State

The backend already has retention primitives:

- `app/domains/files/retention.py` provides `DocumentFileRetentionPlanner`.
  It builds an expired-file plan from `document_files.expires_at`, and
  `mark_expired()` updates metadata to `expired` without deleting objects.
- `app/domains/jobs/artifact_retention.py` provides a legacy jobs artifact
  dry-run planner based on job status and artifact age. This task will not
  expose or expand that legacy artifact surface unless explicitly approved
  later.
- `app/domains/files/router.py` currently exposes upload authorization,
  proxy upload, and single-file metadata lookup only.
- `frontend/src/pages/SystemStatusPage.vue` already gives Admin a read-only
  storage/status surface. `frontend/src/pages/JobDetailPage.vue` already shows
  job file metadata and per-file download actions in job context.

The smallest useful product slice is therefore not a general file manager.
It is an Admin-only retention plan page backed by the existing
`DocumentFileRetentionPlanner`.

## Scope

Implement metadata-only document file retention management:

- Backend:
  - `GET /api/v1/files/retention/plan`
  - `POST /api/v1/files/retention/mark-expired`
- Frontend:
  - New Admin page under the existing Ops/System Status area.
  - Link from System Status storage panel, not a broad top-level file manager
    navigation item.
- Documentation/tests:
  - Update API docs for Files API.
  - Add targeted backend tests and frontend type/build verification.

Out of scope:

- `DELETE /api/v1/files/{file_id}`
- real object deletion
- storage quota cleanup
- scheduled cleanup runner
- retention policy editing
- full file search/library UI
- legacy `/api/v1/jobs` artifact retention UI

## API Design

### `GET /api/v1/files/retention/plan`

Auth: `require_admin_user`.

Behavior:

- Build a plan with `DocumentFileRetentionPlanner(runtime.document_file_repository, retention_days=runtime.settings.oss_file_retention_days)`.
- Return the current plan only; do not mutate metadata.
- Include all candidates for now. If candidate volume becomes a problem, add
  `limit`/`offset` later as a separate task.

Response shape:

```json
{
  "generated_at": "2026-06-04T00:00:00+00:00",
  "retention_days": 90,
  "deletion_supported": false,
  "action_mode": "dry_run",
  "totals": {
    "files_seen": 2,
    "files_with_expires_at": 2,
    "candidate_files": 1,
    "candidate_local_files": 1,
    "candidate_objects": 0,
    "already_deleted_files": 0
  },
  "candidates": [
    {
      "file_id": "file_old",
      "job_id": "docjob_old",
      "file_type": "generated_word",
      "storage_provider": "local_object",
      "bucket": "local-object",
      "object_key": "document-jobs/tenant_default/docjob_old/generated_word/result.docx",
      "size_bytes": 10,
      "status": "uploaded",
      "expires_at": "2026-06-03T00:00:00+00:00",
      "reason": "expires_at=... retention_days=90"
    }
  ]
}
```

### `POST /api/v1/files/retention/mark-expired`

Auth: `require_admin_user`.

Behavior:

- Calls `DocumentFileRetentionPlanner.mark_expired()`.
- Only updates metadata status for current candidates whose status is
  `uploaded`.
- Does not remove local files, object keys, job file rows, or document job rows.
- Records an audit event:
  - `action`: `file.retention_mark_expired`
  - `target_type`: `document_file_retention`
  - `target_id`: `document_files`
  - `details`: candidate count and marked count if supported by current audit
    model; otherwise use the existing narrow fields.

Response shape: same base response as plan, with:

```json
{
  "action_mode": "mark_expired",
  "marked_file_ids": ["file_old"]
}
```

## Backend Files

- `app/domains/files/schemas.py`
  - Add retention response schemas.
- `app/domains/files/router.py`
  - Add Admin-only retention routes before `/{file_id}`.
  - Keep router thin and delegate retention selection to existing planner.
- `app/domains/files/retention.py`
  - Prefer no change. Only add a small method if the router would otherwise
    duplicate candidate-to-response logic.
- `docs/api/files.md`
  - Document the two Admin retention endpoints and non-deletion semantics.
- `tests/test_fastapi_jobs_backend.py`
  - Add API-level auth and metadata-only behavior coverage.
- `tests/test_artifact_retention.py`
  - Keep existing planner tests; extend only if planner behavior changes.

## Frontend Files

- `frontend/src/api/types.ts`
  - Add `FileRetentionCandidateResponse`,
    `FileRetentionPlanResponse`, and `FileRetentionMarkExpiredResponse`.
- `frontend/src/api/files.ts`
  - Add `getRetentionPlan()` and `markRetentionExpired()`.
- `frontend/src/router/index.ts`
  - Add Admin route, proposed path:
    `/system-status/file-retention`.
- `frontend/src/pages/SystemStatusPage.vue`
  - Add a storage panel link to the retention page.
- `frontend/src/pages/FileRetentionPage.vue`
  - New Admin page for totals, policy, candidates, refresh, and metadata-only
    mark-expired action.
- `frontend/src/utils/format.ts`
  - Reuse existing date/bytes helpers; no new helper unless needed.

## UI Behavior

- Empty state: "暂无过期候选文件。"
- Warning copy: "此页面只更新 metadata 状态，不删除本地文件或对象存储内容。"
- Candidate table:
  - `file_id`
  - `job_id` with link to `/jobs/{job_id}` when present
  - `file_type`
  - `storage_provider`
  - `status`
  - `size_bytes`
  - `expires_at`
  - `object_key`
  - `reason`
- Controls:
  - Refresh.
  - Mark expired, enabled only when candidate count is greater than 0.
  - No download/delete/policy edit controls.

## Compatibility

- No persisted schema changes.
- No migration.
- No conversion pipeline changes.
- No changes to document job APIs.
- Adds only Admin API surface and frontend display.

## Risks

- Candidate list can grow large because the repository API currently returns
  all document files. This task accepts that for MVP; pagination is deferred.
- `expires_at` is the source of truth. Files without `expires_at` are not
  candidates.
- Marking metadata `expired` may affect later download eligibility if download
  checks rely on file status. This is intended only for files past
  `expires_at`, and tests must confirm binaries are not removed.

## Review Gate

Do not run `task.py start` or implement code until this design is reviewed and
approved.
