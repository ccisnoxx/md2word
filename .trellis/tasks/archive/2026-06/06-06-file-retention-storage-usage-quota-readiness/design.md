# File retention storage usage quota readiness design

## Current State

Phase 4 retention already has:

- `GET /api/v1/files/retention/plan` for expired metadata candidates.
- `POST /api/v1/files/retention/mark-expired` for metadata-only expiry marking.
- Manual physical delete with dry-run, exact selected IDs, reason, confirmation phrase, local-path containment, metadata preservation, and compact audit.
- Retention policy CRUD for future `expires_at` calculation and dry-run impact preview without historical backfill.
- Health readiness fields for artifact storage backend, local artifact root writability, and local disk free bytes.

This task adds the missing `document_files` usage summary and advisory quota readiness layer.

## Design Decision

Add a dedicated read-only `document_files` storage usage summary under Files API, not a generic health metric extension.

Reasons:

- Health metrics should stay coarse process/readiness state.
- Storage usage is domain-specific because it depends on `document_files` statuses, retention expiration, and physical-delete eligibility categories.
- Files API already owns Admin-only retention operations.
- The UI can reuse `/system-status/file-retention` while keeping usage summary separate from physical delete controls.

## Implemented API

Endpoint:

```http
GET /api/v1/files/storage/usage
```

Authentication:

- Bearer JWT.
- Admin only.

Behavior:

- Reads `document_files` metadata through `DocumentFileRepositoryProtocol`.
- Reads artifact storage readiness context from `HealthService.build_dependency_checks()`.
- Does not mutate metadata.
- Does not mark expired.
- Does not preview or execute physical delete.
- Does not call storage delete adapters.
- Does not write audit by default because the endpoint is read-only.

Route placement:

- Added before `/{file_id}` in `app/domains/files/router.py`.

## Response Model

Implemented schema names:

- `FileStorageUsageResponse`
- `FileStorageUsageGroupResponse`

Top-level response includes:

- `generated_at`
- `artifact_storage`
- `artifact_root_writable`
- `artifact_disk_free_bytes`
- `totals`
- `reclaim`
- `quota`
- `by_storage_provider`
- `by_file_type`
- `by_status`

Group response fields:

| Field | Meaning |
| --- | --- |
| `key` | Provider, file type, or status value. |
| `file_count` | Matching metadata rows. |
| `size_bytes` | Sum of `DocumentFileRecord.size_bytes`. |
| `expired_count` | Rows with `expires_at <= generated_at` and not `deleted`. |
| `expired_size_bytes` | Sum of expired rows. |
| `estimated_reclaimable_count` | Rows that are `status=expired`, expired by time, local/local-object, and have `object_key`. |
| `estimated_reclaimable_size_bytes` | Metadata-estimated bytes for those rows. |

Quota status values:

- `not_configured`
- `ok`
- `warning`
- `exceeded`

This implementation does not add quota settings, so API responses return `not_configured`. The service has internal advisory calculation support for future settings, but upload behavior is unchanged.

## Aggregation Semantics

Input source:

- `DocumentFileRecord.size_bytes` is the source for usage estimates.
- Rows with `status=deleted` are counted separately as metadata history, not active storage pressure.
- The implementation does not crawl the filesystem or verify every object path.

Expiration:

- A file is time-expired when `expires_at is not None and expires_at <= generated_at`.
- `status=deleted` rows are not reclaim candidates.
- `status=expired` plus expired time is required for manual physical-delete eligibility.

Estimated reclaim categories:

| Category | Rule |
| --- | --- |
| `estimated_reclaimable` | `status=expired`, expired by time, `storage_provider in {"local_file", "local_object"}`, and non-empty `object_key`. |
| `unsupported_storage` | `status=expired`, expired by time, provider currently not supported for physical deletion, for example `s3`. |
| `blocked_missing_object_key` | `status=expired`, expired by time, local/local-object provider, empty `object_key`. |
| `blocked_not_expired_status` | Time-expired but status is still `uploaded` or `pending_upload`; these need mark-expired or normal upload completion first. |
| `deleted_metadata` | `status=deleted`; counted for history, not reclaim. |

The response intentionally says `estimated_reclaimable`, not `deletable`, because actual delete outcomes still require selected-file dry-run through `/retention/delete-preview`.

## Service Boundary

Implemented module:

- `app/domains/files/storage_usage.py`

Implemented service:

- `DocumentFileStorageUsageReporter`

Properties:

- Read-only.
- Repository-protocol based.
- No concrete file/sqlite/mysql adapter dependency.
- No filesystem crawl.
- No audit side effect.
- No upload authorization dependency.

Runtime wiring:

- The router builds the reporter from current runtime dependencies.
- The service is not added to `AppRuntime` because this first slice has one caller.

## Frontend Scope

Implemented on `/system-status/file-retention`.

Added:

- Storage usage summary cards.
- Advisory quota status tag.
- Artifact disk free/writable context.
- Grouped tables by provider, file type, and status.
- Copy that usage is metadata-only and deletion still requires dry-run + confirmation.

Not added:

- Delete-all button.
- Auto-selection based on usage summary.
- Upload-blocking banner.
- S3 cleanup controls.

## Documentation

Updated:

- `docs/api/files.md`
- `docs/api/health.md`
- `docs/api/openapi.json`

## Compatibility

- Additive API only.
- No existing retention, policy, upload, health, or physical-delete behavior changes.
- Works across file/sqlite/mysql metadata backends because it reads `DocumentFileRepositoryProtocol.list_document_files()`.
- Current `size_bytes` remains the usage estimate source; old metadata with stale size values may produce approximate output.

## Risks

- Metadata-estimated bytes may differ from actual disk/object-store bytes if files are missing or externally changed.
- Full-list scans are acceptable for an Admin manual readiness page, but not for high-volume continuous monitoring.
- Quota status could be misread as enforcement; UI and docs state advisory-only.
- Combining usage summary and delete controls on one page can encourage unsafe action; visual separation and no auto-selection are required.
