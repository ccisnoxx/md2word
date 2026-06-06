# Ops provider cancellation safety contract design

## Boundary

This task implements fake provider cancellation only. It creates no MinerU cancellation client method and calls no external provider API.

Fake cancellation is separate from existing local job cancellation:

- It does not call `DocumentJobService.cancel_job()`.
- It does not call legacy `JobLifecycleService.cancel_job()`.
- It does not mutate queues, stage messages, job metadata, document files, or provider state.
- It only writes a compact audit event for eligible non-deduped fake-cancel attempts.

## API Contract

Add:

```text
POST /api/v1/ops/provider-cancellations/preview
POST /api/v1/ops/provider-cancellations/fake-cancel
```

Auth:

- Bearer JWT.
- Admin only.

Preview request:

```json
{
  "target_type": "document_job",
  "target_id": "docjob_123",
  "provider": "mineru",
  "dedupe_window_minutes": 60
}
```

Fake-cancel request:

```json
{
  "target_type": "document_job",
  "target_id": "docjob_123",
  "provider": "mineru",
  "reason": "upstream cancellation drill",
  "confirmation": "FAKE CANCEL PROVIDER OPERATION",
  "dedupe_window_minutes": 60
}
```

Validation:

- `target_type`: `document_job` or `legacy_job`.
- `provider`: `mineru` only.
- `dedupe_window_minutes`: 1..1440.
- Fake-cancel requires exact confirmation phrase and non-empty reason.

## Eligibility

### Document job

Eligible when:

- job exists.
- job is not archived.
- status is `running` or `queued`.
- `mineru_batch_id` exists.

Missing gates:

- `target_not_found`
- `target_archived`
- `status_not_provider_cancelable`
- `provider_operation_id_missing`

### Legacy job

Eligible when:

- job exists.
- `source_kind=source_pdf`.
- projected status is not `completed`, `failed`, or `canceled`.
- `read_mineru_batch_id()` exists.

Missing gates:

- `target_not_found`
- `source_kind_not_source_pdf`
- `status_terminal`
- `provider_operation_id_missing`

## Response

```json
{
  "generated_at": "2026-06-07T00:00:00+00:00",
  "action_mode": "fake_cancel",
  "provider": "mineru",
  "confirmation_phrase": "FAKE CANCEL PROVIDER OPERATION",
  "dedupe_window_minutes": 60,
  "target": {
    "target_type": "document_job",
    "target_id": "docjob_123",
    "exists": true,
    "status": "running",
    "stage": "parsing",
    "summary": {"archived": false}
  },
  "provider_operation": {
    "provider": "mineru",
    "operation_id": "batch_123",
    "data_id": "docjob_123",
    "operation_type": "batch_extract"
  },
  "eligible": true,
  "missing_gates": [],
  "outcome": "fake_canceled",
  "dedupe_key": "mineru:document_job:docjob_123:batch_123",
  "audit_event_written": true,
  "safety": {
    "real_provider_cancel_executed": false,
    "provider_calls_executed": false,
    "local_job_mutated": false,
    "queue_mutated": false,
    "cleanup_executed": false,
    "delete_executed": false,
    "conversion_workflow_executed": false,
    "audit_events_written": true
  }
}
```

Outcomes:

| Outcome | Meaning |
| --- | --- |
| `cancelable` | Preview-only eligible target. |
| `fake_canceled` | Fake cancellation audit was recorded. |
| `deduped` | Matching fake cancellation audit exists inside dedupe window. |
| `ineligible` | Target exists but missing gates block cancellation. |
| `failed` | Unexpected local audit/outbox failure. |

## Service Placement

Add:

- `app/domains/ops/provider_cancellation.py`
  - Reads document_jobs and legacy jobs metadata.
  - Builds provider operation summary from stored MinerU IDs only.
  - Checks recent audit event dedupe keys.
  - Builds preview/fake-cancel reports.

Extend:

- `app/domains/ops/schemas.py`
- `app/domains/ops/router.py`
- `app/domains/ops/recovery_actions.py`
- `docs/api/ops.md`
- `docs/api/openapi.json`
- `tests/test_fastapi_jobs_backend.py`

## Audit

For fake-cancel, write one compact event:

- `action=ops.provider_cancellation_fake`
- `target_type=provider_operation`
- `target_id=<provider>:<target_type>:<target_id>`

Reason includes:

- human reason.
- provider.
- target type and target ID.
- operation ID and data ID.
- dedupe key.
- outcome.

Do not store provider credentials, callback seed, full URLs, local paths, prompt text, file bytes, or provider response bodies.

## Registry Update

`provider.cancel` becomes available for fake cancellation:

- `available=True`
- `requires_reason=True`
- `requires_confirmation=True`
- `dry_run_supported=True`
- `mutates_metadata=True` only because audit/outbox metadata is written.
- `calls_provider=False`
- `audit_action=ops.provider_cancellation_fake`
- known gap: real provider cancellation API/semantics are still unimplemented.

## Compatibility

- Additive API only.
- No database/file schema migration.
- Existing document job and legacy job cancellation behavior remains unchanged.

## Risks

- Operators could misread fake cancellation as real provider cancellation; response fields and docs must say real provider cancellation was not executed.
- Dedupe by audit reason is enough for a fake contract but not for real provider execution.
- Real provider cancellation must be a later provider-specific task with docs/API verification and fake-client success/error/timeout coverage.
