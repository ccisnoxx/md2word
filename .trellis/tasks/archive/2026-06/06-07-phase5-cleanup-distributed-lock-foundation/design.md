# Phase 5 cleanup distributed lock foundation design

## Current State

- Cleanup run now has durable history and signed cleanup plan.
- There is still no lock boundary for future scheduler/manual automation runners.
- Existing physical-delete and cleanup-run execution remain exact-target and confirmation-gated.

## Design

### Domain

Add `app/domains/files/cleanup_lock.py`.

Primary model:

- `FileRetentionCleanupLockRecord`
  - `lock_name`
  - `owner_id`
  - `fencing_token`
  - `status`: `active` or `released`
  - `acquired_at`
  - `expires_at`
  - `heartbeat_at`
  - `released_at`
  - `metadata`

Service:

- `acquire(owner_id, ttl_seconds, now=None)`
- `refresh(owner_id, fencing_token, ttl_seconds, now=None)`
- `release(owner_id, fencing_token, now=None)`
- `get_status(now=None)`

Conflict errors:

- `cleanup_lock_already_held`
- `cleanup_lock_fencing_token_mismatch`
- `cleanup_lock_not_active`
- `cleanup_lock_expired`

### Persistence

Add repository protocol and adapters:

- file: `var/config/file_retention_cleanup_locks.json`
- sqlite table: `file_retention_cleanup_locks`
- mysql table: `file_retention_cleanup_locks`

Store full payload JSON plus indexed columns `lock_name`, `status`, `owner_id`, `fencing_token`, `expires_at`, `updated_at`.

### Runtime Wiring

- Add repository to `PersistenceAdapters`.
- Add repository field to `AppRuntime`.
- Wire build runtime and test runtime.
- No new public API routes in this slice; future runner/API task can consume the service.

### Safety

- Lock service never calls file deletion, provider cancellation, alert delivery, parser, translation or renderer.
- Lock read and transitions do not write audit events in this foundation slice.
- Expiry is evaluated by service based on `expires_at`; expired takeover writes a new active record with incremented fencing token.

## Tradeoffs

- A metadata lock is not a database-native distributed lock. It is sufficient as a foundation contract and makes future scheduler behavior auditable/testable before any autonomous cleanup.
- Single-row per lock name is simpler than an append-only lock event stream. Durable run history remains the audit surface for actual cleanup execution.
