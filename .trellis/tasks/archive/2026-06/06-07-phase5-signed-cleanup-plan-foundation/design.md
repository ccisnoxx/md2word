# Phase 5 signed cleanup plan foundation design

## Current State

- `FileRetentionCleanupRunService.preview()` returns an in-memory report with `run_id` and `preview_hash`.
- `FileRetentionCleanupRunHistoryService.record_preview()` persists a compact history record.
- `execute` can accept optional `run_id`; when present, the backend updates the same history record.
- Physical deletion is still guarded by selected-file physical-delete validation and confirmation phrase.

## Design

### Data Model

Add `FileRetentionSignedCleanupPlan` to `app/domains/files/cleanup_history.py`.

Fields:

- `plan_id: str`
- `run_id: str`
- `preview_hash: str`
- `requested_file_ids: list[str]`
- `max_files: int`
- `created_at: datetime`
- `expires_at: datetime`
- `signature: str`
- `signature_algorithm: Literal["hmac-sha256"]`
- `safety: dict[str, bool]`

`FileRetentionCleanupRunHistoryRecord` gains optional `cleanup_plan`.

### Signature

Use deterministic HMAC-SHA256 over compact JSON payload:

```text
run_id
preview_hash
requested_file_ids
max_files
created_at
expires_at
```

Secret:

- Use `settings.jwt_secret_key` as existing local secret input.
- Purpose-bind the HMAC key with a fixed namespace string to avoid mixing JWT token use and cleanup plan signing semantics.
- Do not expose secret in API, logs, audit, docs, or tests.

Plan ID:

- `cleanup_plan_<first 16 chars of signature hex>`.

Expiry:

- Fixed short TTL in code for this foundation slice: 30 minutes.
- Future slice may make this configurable if needed.

### Service Flow

Preview:

1. Build existing cleanup run report.
2. Create signed plan from report.
3. Save preview history with plan.
4. Return response with `cleanup_plan`.

Execute:

1. If `run_id` is provided, load history.
2. If request includes `plan_id` or `plan_signature`, require both and validate against history plan.
3. Validation checks exact run, plan, file_ids, max_files, preview_hash, signature, and expiry.
4. On validation failure, record failed history and return error before physical delete.
5. Existing `preview_hash` validation still runs inside `FileRetentionCleanupRunService.execute()`.
6. Save executed history with plan.

Compatibility:

- Old clients that only send `run_id + preview_hash` still work.
- Responses always include `cleanup_plan` after preview/execute.

### API Schema

- `FileRetentionCleanupRunExecuteRequest` gains:
  - `plan_id: str | None`
  - `plan_signature: str | None`
- `FileRetentionCleanupRunResponse` gains:
  - `cleanup_plan: FileRetentionSignedCleanupPlanResponse | None`
- `FileRetentionCleanupRunHistoryResponse` gains:
  - `cleanup_plan: FileRetentionSignedCleanupPlanResponse | None`
- `FileRetentionCleanupRunSafetyResponse` gains:
  - `signed_plan_created`
  - `signed_plan_verified`

### Frontend

- Add TS contract fields.
- Pass `cleanup_plan.plan_id` and `cleanup_plan.signature` from preview into execute.
- Display plan ID, expiry, and signature algorithm in cleanup run result/history detail.

### Safety

- No new physical-delete capability.
- No scheduler loop.
- No external provider calls.
- No S3 delete.
- No local paths or object keys in plan.
- Failed plan validation happens before physical delete.

## Tradeoffs

- Reusing cleanup history persistence avoids creating a fourth repository family and keeps the slice small.
- Fixed TTL avoids new config churn; if operational need appears, add explicit config later.
- HMAC uses an existing local secret source for this foundation slice; a later production hardening slice can move to a dedicated secret reference.
