# File retention physical delete safety contract design

## Current State

Existing `file-retention-management` added a metadata-only foundation:

- `GET /api/v1/files/retention/plan`
- `POST /api/v1/files/retention/mark-expired`
- `frontend/src/pages/FileRetentionPage.vue`
- `DocumentFileRetentionPlanner` based on `document_files.expires_at`

Current code deliberately does not remove local files, object-store files, S3 objects, metadata rows, task rows, or object keys. Current audit support is compact: `AuditEvent` has `reason` but no structured `details`.

## Design Decision

Implement manual physical deletion for `document_files` only, and only after a file has already been marked `expired`.

First version supports:

- `storage_provider=local_file`
- `storage_provider=local_object`

First version does not support:

- `storage_provider=s3`
- scheduled cleanup
- retention policy editing
- file library/search
- quota enforcement
- legacy `/api/v1/jobs` local cleanup

## API Design

### `POST /api/v1/files/retention/delete-preview`

Auth: `require_admin_user`.

Request:

```json
{
  "file_ids": ["file_a", "file_b"]
}
```

Behavior:

- Validate `file_ids`.
- Re-read records from `document_file_repository`.
- Return per-file outcome preview.
- Do not mutate metadata.
- Do not delete binaries.
- Do not write audit.

Response:

```json
{
  "action_mode": "delete_preview",
  "generated_at": "2026-06-06T00:00:00+00:00",
  "requested_file_ids": ["file_a", "file_b"],
  "confirmation_phrase": "DELETE EXPIRED FILES",
  "totals": {
    "requested": 2,
    "deletable": 1,
    "skipped": 1,
    "deleted": 0,
    "failed": 0
  },
  "items": [
    {
      "file_id": "file_a",
      "job_id": "docjob_a",
      "file_type": "generated_word",
      "storage_provider": "local_object",
      "status_before": "expired",
      "status_after": "expired",
      "object_key": "document-jobs/tenant_default/docjob_a/generated_word/result.docx",
      "size_bytes": 10,
      "outcome": "deletable",
      "reason": "eligible_expired_file",
      "deleted": false,
      "metadata_updated": false
    }
  ]
}
```

### `POST /api/v1/files/retention/delete-expired`

Auth: `require_admin_user`.

Request:

```json
{
  "file_ids": ["file_a"],
  "reason": "manual retention cleanup",
  "confirmation": "DELETE EXPIRED FILES"
}
```

Behavior:

- Validate `file_ids`, `reason`, and `confirmation`.
- Re-read records immediately before deletion.
- Delete only eligible local/local_object binaries.
- Treat missing local object as idempotent if metadata is still eligible.
- Update metadata to `deleted` only for `deleted` or `already_missing` local outcomes.
- Keep metadata rows and `object_key`.
- Skip unsupported S3.
- Record one compact audit event after the execution attempt.

Response shape: same as preview, with `action_mode=delete_execute`, mutation outcomes, and compact totals.

## Outcome Semantics

| Outcome | Meaning | Metadata update |
| --- | --- | --- |
| `deletable` | Preview-only eligible local/local_object file. | No |
| `deleted` | Local/local_object file existed and was removed. | `status=deleted` |
| `already_missing` | Eligible local/local_object file was already absent. | `status=deleted` |
| `skipped_not_found` | No metadata record exists. | No |
| `skipped_not_expired_status` | Status is not `expired`. | No |
| `skipped_not_expired_time` | `expires_at` is missing or still in the future. | No |
| `skipped_already_deleted` | Metadata already says `deleted`. | No |
| `skipped_unsupported_storage` | S3 or unknown provider in first slice. | No |
| `skipped_missing_object_key` | Local/local_object metadata has no `object_key`. | No |
| `failed` | Unexpected local deletion or metadata update failure. | No |

## Backend Files

- `app/domains/files/schemas.py`
  - Add delete request/response schemas.
- `app/domains/files/retention.py`
  - Add dataclasses/service logic for selected-file preview and execution, or a nearby `retention_delete.py` if it becomes clearer.
  - Keep path deletion out of router.
- `app/domains/files/router.py`
  - Add static routes before `/{file_id}`.
  - Keep router responsible for auth, trace id, service call, audit call, and response mapping.
- `app/domains/files/service.py`
  - Add a narrow method for deleting local/local_object content by `DocumentFileRecord`.
  - Use existing `resolve_local_object_path()` guard.
  - Do not add S3 deletion in this task.
- `docs/api/files.md`
  - Document preview and execution semantics.
- `docs/api/openapi.json`
  - Regenerate if API schema changes.

## Frontend Files

- `frontend/src/api/types.ts`
  - Add request/response types.
- `frontend/src/api/files.ts`
  - Add `previewRetentionDelete()` and `deleteExpiredRetentionFiles()`.
- `frontend/src/pages/FileRetentionPage.vue`
  - Add candidate selection.
  - Add preview panel.
  - Add delete dialog requiring reason and confirmation phrase.
  - Add outcome table.
  - Keep existing metadata-only mark-expired behavior intact.

## Audit

Use existing `AuditService.record()`:

- `action=file.retention_physical_delete`
- `target_type=document_file_retention`
- `target_id=document_files`
- `reason` compact example:
  - `reason=manual cleanup requested=3 deleted=2 already_missing=1 skipped=0 failed=0`

Do not store local absolute paths, file content, prompts, responses, tokens, or secrets.

## Compatibility

- Additive API change.
- No persisted schema change.
- Existing retention plan and mark-expired response remains compatible.
- Existing download logic already rejects non-`uploaded` files, so `deleted` metadata will not be downloadable.

## Risks

- Physical deletion is irreversible for local binaries; this is mitigated by expired-only eligibility, dry-run, explicit IDs, reason, confirmation phrase, and audit.
- Current repository APIs list/read in memory; acceptable for 50-item manual batches.
- S3 remains unsupported in first version; this prevents accidental real cloud deletion without provider-specific review.
- Audit details are compact. A later task should add structured audit details if compliance requires per-file durable evidence beyond reason text.

## Review / Start

User approved proceeding from the gap audit into this implementation task on 2026-06-06. After these planning artifacts are written and validated, run `task.py start` and implement exactly this scope.
