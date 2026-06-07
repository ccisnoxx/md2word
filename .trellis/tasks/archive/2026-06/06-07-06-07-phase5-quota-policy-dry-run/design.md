# Phase 5 quota policy dry run design

## Current State

- `GET /api/v1/files/storage/usage` returns Admin-only metadata-estimated usage and an advisory `quota` object.
- `DocumentFileStorageUsageReporter` already supports quota calculation when `quota_bytes` and `warning_threshold_ratio` are provided, but router wiring does not currently provide staged quota settings.
- `POST /api/v1/files/upload-url` validates PDF metadata and max upload bytes, then creates a `document_files` record and writes `file.upload_authorize` audit.
- No quota policy currently blocks upload authorization.

## Backend Contract

Add settings:

- `files_quota_policy_enabled: bool = False`
- `files_quota_policy_dry_run: bool = True`
- `files_quota_bytes: int = 0`
- `files_quota_warning_threshold_ratio: float = 0.8`
- `files_quota_block_threshold_ratio: float = 1.0`

Add endpoint:

```text
POST /api/v1/files/quota-policy/dry-run
```

Request:

- `size_bytes`: proposed upload size, `ge=0`.
- `file_type`: optional, defaults to `source_pdf`.
- `filename`: optional display/debug context only.

Response:

- generated time and policy status.
- current/projected used bytes and ratios.
- `would_warn` and `would_block`.
- reason list and safety flags.

Authorization:

- Admin-only via existing `require_admin_user`.

Side effects:

- No metadata writes.
- No audit writes.
- No upload authorization creation.
- No object storage/S3/provider calls.
- No parser/translation/Word workflow calls.

## Service Shape

Create `app/domains/files/quota_policy.py` as a small pure service:

- It receives settings and a `DocumentFileRepositoryProtocol`.
- It sums current active usage from `document_files` metadata.
- It evaluates a proposed upload size against staged settings.
- It returns dataclass records mapped by the router into Pydantic response schemas.

The service intentionally does not call `FileUploadService.create_upload_authorization` so dry-run cannot accidentally create records or audit events.

## Frontend Contract

Reuse `frontend/src/api/files.ts`:

- Add `dryRunQuotaPolicy(payload)`.
- Add TS request/response types in `frontend/src/api/types.ts`.

Add a compact panel inside `FileRetentionPage.vue` storage section:

- Proposed upload size input.
- Optional filename/file type.
- Dry-run button.
- Result cards for current/projected usage, `would_warn`, `would_block`, and safety flags.

## Compatibility

- Existing storage usage response stays compatible.
- Existing upload authorization behavior is unchanged.
- New settings default to disabled/not configured, so existing environments do not change behavior.

## Rollback

- Remove quota policy settings, service, schemas, route, frontend types/API/UI, tests, docs, and OpenAPI snapshot changes.
