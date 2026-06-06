# Ops recovery action safety registry design

## Boundary

This task adds read-only action governance. It does not execute recovery, cancellation, provider calls, alert delivery, cleanup, scheduler loops, physical deletion, or file mutation.

## API Contract

Add:

```text
GET /api/v1/ops/recovery-actions
POST /api/v1/ops/recovery-actions/preview
```

Authentication:

- Bearer JWT.
- Admin only.

## Registry Response

`GET /api/v1/ops/recovery-actions` returns:

- `generated_at`
- `actions`
- `safety`

Each `actions[]` entry includes:

- stable identity: `action_id`, `label`, `category`, `target_type`
- availability: `available`, `known_gaps`, `suggested_route`
- gates: `requires_admin`, `requires_reason`, `requires_confirmation`, `dry_run_supported`
- risk flags: `mutates_metadata`, `mutates_queue`, `calls_provider`, `sends_notification`, `deletes_data`
- audit contract: `audit_action`

## Preview Request

```json
{
  "action_id": "document_job.retry",
  "target_type": "document_job",
  "target_id": "docjob_123"
}
```

## Preview Response

```json
{
  "generated_at": "2026-06-07T00:00:00+00:00",
  "action": {},
  "target": {
    "target_type": "document_job",
    "target_id": "docjob_123",
    "exists": true,
    "status": "failed",
    "stage": "failed",
    "summary": {}
  },
  "eligible": true,
  "missing_gates": [],
  "warnings": [],
  "risk_flags": {},
  "audit_action": "document_job.retry",
  "safety": {
    "read_only": true,
    "execution_performed": false,
    "metadata_mutated": false,
    "queue_mutated": false,
    "provider_calls_executed": false,
    "notification_delivery_executed": false,
    "cleanup_executed": false,
    "delete_executed": false,
    "audit_events_written": false
  }
}
```

## Action Catalog

| Action | Target | Availability | Notes |
| --- | --- | --- | --- |
| `document_job.retry` | `document_job` | available | Eligible for failed, unarchived document jobs; existing execution remains separate. |
| `document_job.cancel` | `document_job` | available | Eligible for pending/queued/running, unarchived document jobs; local state only. |
| `document_job.archive` | `document_job` | available | Eligible for succeeded/failed/canceled document jobs. |
| `legacy_job.retry` | `legacy_job` | available | Existing legacy API mutates queue/stage state; preview only. |
| `legacy_job.cancel` | `legacy_job` | available | Existing legacy API deletes replayable stage messages and marks job canceled; preview only. |
| `legacy_job.recover_mineru_result` | `legacy_job` | available if MinerU token configured | Existing API queries provider; preview must not. |
| `legacy_job.cleanup_local_files` | `legacy_job` | available | Existing API deletes local work dir; preview must not return local paths. |
| `provider.cancel` | `provider_operation` | unavailable | Local MinerU client has no cancel method; docs/API verification required. |
| `alert.delivery` | `alert` | unavailable | Delivery config/dedupe/rate-limit/audit not implemented. |
| `file_retention.automated_cleanup_execute` | `cleanup_run` | unavailable | Scheduler/run history/lock/signed plan not implemented. |

## Preview Rules

### `document_job`

Source: `runtime.document_job_repository.get_document_job(target_id)`.

Eligibility:

- `document_job.retry`: exists, not archived, status `failed`.
- `document_job.cancel`: exists, not archived, status `pending`, `queued`, or `running`.
- `document_job.archive`: exists, not archived, status `succeeded`, `failed`, or `canceled`.

Target summary can include safe fields:

- `status`
- `stage`
- `retry_count`
- `archived`
- `created_by`
- `updated_at`

### `legacy_job`

Source: `runtime.job_repository.get_job(target_id)`.

Eligibility:

- `legacy_job.retry`: existing workflow allows failed or canceled states per current retry policy; preview should conservatively require `failed`.
- `legacy_job.cancel`: projected status not terminal `completed`, `failed`, or `canceled`.
- `legacy_job.recover_mineru_result`: source PDF job, MinerU batch ID present, MinerU token configured, not terminal completed/canceled.
- `legacy_job.cleanup_local_files`: terminal job `completed`, `failed`, or `canceled`.

Target summary must not include local paths, object keys, prompts, tokens, or callback seeds.

### Candidate-only targets

Provider cancellation, alert delivery, and automated cleanup execution can be previewed as unavailable action entries. If previewed, they should not require a real target record. They should return `eligible=false` and `missing_gates` explaining why execution is not available.

## Backend Placement

Add a small `app/domains/ops/` package:

- `schemas.py` for Pydantic response/request contracts.
- `recovery_actions.py` for action registry and preview service.
- `router.py` for thin FastAPI routes.

Add router inclusion in `app/api/v1/router.py`.

## Frontend Placement

Minimal frontend integration:

- Add TypeScript contracts.
- Add API wrapper.
- Add read-only action safety section to `OpsDashboardPage.vue`.

No execution buttons are added.

## Tests

Targeted tests in `tests/test_fastapi_jobs_backend.py`:

- Admin can list registry.
- Operator is rejected.
- Admin can preview eligible document job retry without mutation/audit/provider calls.
- Admin can preview ineligible document job cancel for terminal job.
- Admin can preview legacy MinerU recovery and see provider-call risk without executing provider query.
- Candidate actions are listed as unavailable with known gaps.

## Safety

- Read-only endpoint only.
- No audit event by default because status reads do not mutate state.
- Explicit safety object says no execution, mutation, provider call, notification delivery, cleanup, delete, or audit write occurred.
- No background task dispatch.
- No calls to `runtime.stage_service`, `runtime.stage_dispatcher`, lifecycle execution services, file delete services, provider clients, or notification integrations.

## Rollback

Remove the `app/domains/ops` package, router include, frontend read-only integration, tests, docs/OpenAPI changes, and task archive.
