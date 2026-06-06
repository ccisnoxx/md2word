# File retention automated cleanup execution contract design

## Boundary

This task adds a manual Admin-triggered cleanup run execution contract. It does not add a scheduler daemon, cron loop, background worker, or policy-enforced automatic cleanup.

The contract is intentionally an execution wrapper around the existing manual physical-delete primitive:

- selection remains exact `file_ids`.
- preview is required.
- execute verifies the preview hash.
- execute calls `FileUploadService.execute_retention_physical_delete()`.
- S3 remains unsupported by the physical-delete primitive and therefore remains skipped, never deleted.

## API Contract

Add:

```text
POST /api/v1/files/retention/cleanup-runs/preview
POST /api/v1/files/retention/cleanup-runs/execute
```

Auth:

- Bearer JWT.
- Admin only.

Preview request:

```json
{
  "file_ids": ["file_a", "file_b"],
  "max_files": 50
}
```

Execute request:

```json
{
  "file_ids": ["file_a", "file_b"],
  "max_files": 50,
  "preview_hash": "sha256:...",
  "reason": "monthly retention cleanup",
  "confirmation": "EXECUTE AUTOMATED RETENTION CLEANUP"
}
```

Validation:

- `file_ids` follows the existing physical-delete constraints: non-empty, unique, non-blank, max 50.
- `max_files`: 1..50. Request is rejected if `len(file_ids) > max_files`.
- Execute requires reason and exact confirmation phrase.
- Execute re-generates the physical-delete preview and rejects mismatched `preview_hash`.

## Response

```json
{
  "run_id": "cleanup_run_xxx",
  "generated_at": "2026-06-07T00:00:00+00:00",
  "action_mode": "cleanup_execute",
  "confirmation_phrase": "EXECUTE AUTOMATED RETENTION CLEANUP",
  "preview_hash": "sha256:...",
  "requested_file_ids": ["file_a"],
  "max_files": 50,
  "physical_delete": {
    "action_mode": "delete_execute",
    "totals": {}
  },
  "safety": {
    "scheduler_loop_executed": false,
    "provider_calls_executed": false,
    "s3_delete_executed": false,
    "physical_delete_executed": true,
    "physical_delete_contract_reused": true,
    "audit_events_written": true
  }
}
```

## Preview Hash

The preview hash is computed from:

- requested file IDs.
- physical-delete preview item outcomes.
- storage provider.
- status before/after.
- object key.
- size bytes.

It excludes timestamps and run IDs so a repeated preview over unchanged targets produces the same hash.

## Service Placement

Add:

- `app/domains/files/cleanup_execution.py`
  - Validates cleanup run caps.
  - Builds preview reports from existing physical-delete preview.
  - Computes preview hash.
  - Executes by first validating current hash and then delegating to existing physical-delete execution.

Extend:

- `app/domains/files/schemas.py`
- `app/domains/files/router.py`
- `app/domains/ops/recovery_actions.py`
- `docs/api/files.md`
- `docs/api/ops.md`
- `docs/api/openapi.json`
- `tests/test_fastapi_jobs_backend.py`

## Audit

Execute writes one compact audit event:

- `action=file.retention_automated_cleanup_execute`
- `target_type=document_file_retention_cleanup_run`
- `target_id=<cleanup_run_id>`

Reason includes:

- human reason.
- requested count.
- preview hash.
- physical-delete totals.

Do not store file bytes, local paths, secrets, prompt text, provider response bodies, full object bodies, or raw preview payload.

## Registry Update

`file_retention.automated_cleanup_execute` becomes available for this manual cleanup run contract:

- `available=True`
- `requires_reason=True`
- `requires_confirmation=True`
- `dry_run_supported=True`
- `mutates_metadata=True`
- `deletes_data=True`
- `audit_action=file.retention_automated_cleanup_execute`
- known gap: no scheduler loop or autonomous policy executor exists.

## Compatibility

- Additive API only.
- No database/file schema migration.
- Existing retention plan, mark-expired, policy CRUD, storage usage, and physical-delete APIs remain compatible.

## Risks

- The name "automated cleanup" can imply unsupervised scheduling; docs and safety metadata must say this is manual cleanup run execution only.
- Hash mismatch can block stale execution; this is intentional because target state changed after preview.
- Existing physical-delete response includes object_key; this endpoint reuses that response because it is already part of the approved Admin physical-delete safety contract.
