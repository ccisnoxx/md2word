# Ops alert delivery outbox safety contract design

## Boundary

This task adds a fake/local delivery outbox contract for active Ops alerts. It does not integrate with Slack, email, webhook, PagerDuty, SMS, or any external service.

The durable record is the existing append-only audit event. No new persistence schema is introduced.

## API Contract

Add to the existing Ops router namespace:

```text
POST /api/v1/ops/alert-deliveries/preview
POST /api/v1/ops/alert-deliveries/fake-send
```

Auth:

- Bearer JWT.
- Admin only.

Request:

```json
{
  "alert_codes": ["stage_spool_failed_messages_present"],
  "channel": "local_outbox",
  "reason": "ops drill",
  "confirmation": "SEND FAKE OPS ALERTS",
  "dedupe_window_minutes": 60
}
```

Preview ignores `reason` / `confirmation` if present but returns the required confirmation phrase.

Fake send requires `reason` and exact `confirmation`.

Validation:

- `alert_codes`: 1..10, trimmed, unique.
- Every code must match an alert currently returned by `HealthService.build_ops_alerts_response()`.
- `channel` first version only supports `local_outbox`.
- `dedupe_window_minutes`: 1..1440, default 60.

## Response

```json
{
  "generated_at": "2026-06-07T00:00:00+00:00",
  "action_mode": "fake_send",
  "channel": "local_outbox",
  "confirmation_phrase": "SEND FAKE OPS ALERTS",
  "dedupe_window_minutes": 60,
  "requested_alert_codes": ["stage_spool_failed_messages_present"],
  "delivery_id": "alert_delivery_xxx",
  "totals": {
    "requested": 1,
    "deliverable": 0,
    "fake_delivered": 1,
    "deduped": 0,
    "skipped": 0,
    "failed": 0,
    "audit_events_written": 1
  },
  "items": [
    {
      "alert_code": "stage_spool_failed_messages_present",
      "severity": "critical",
      "source": "stage_spool",
      "title": "Failed stage messages present",
      "outcome": "fake_delivered",
      "dedupe_key": "stage_spool_failed_messages_present:local_outbox",
      "reason": "fake local outbox delivery recorded",
      "audit_event_written": true
    }
  ],
  "safety": {
    "external_delivery_executed": false,
    "provider_calls_executed": false,
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
| `deliverable` | Preview-only selected active alert. |
| `fake_delivered` | Fake outbox attempt recorded with audit. |
| `deduped` | Matching delivery audit already exists inside dedupe window. |
| `skipped_not_active` | Alert code is not active in current health ops-alerts response. |
| `skipped_rate_limited` | Request exceeds batch cap or future rate-limit rule. |
| `failed` | Unexpected local audit/outbox error. |

## Service Placement

Add:

- `app/domains/ops/alert_delivery.py`
  - Validates exact alert codes.
  - Reads current alerts from `runtime.health_service`.
  - Checks recent audit events for dedupe.
  - Builds preview/fake delivery reports.
- Extend `app/domains/ops/schemas.py` with request/response models.
- Extend `app/domains/ops/router.py` with two Admin-only endpoints.

## Audit

For `fake-send`, write one compact audit event per non-deduped batch:

- `action=ops.alert_delivery_fake`
- `target_type=ops_alert_delivery`
- `target_id=<delivery_id>`
- reason includes:
  - `channel`
  - sorted selected alert codes
  - `fake_delivered`
  - `deduped`
  - human reason

Do not store webhook URLs, credentials, full readiness payloads, local paths, prompt text, file bytes, or provider response bodies.

## Registry Update

Change `alert.delivery` in `OPS_RECOVERY_ACTIONS`:

- `available=True`
- `requires_reason=True`
- `requires_confirmation=True`
- `mutates_metadata=True`
- `sends_notification=False`
- `audit_action="ops.alert_delivery_fake"`
- known gap: real external delivery is still not implemented.

## Compatibility

- Additive API.
- No database/file schema migration.
- Existing health and recovery action registry endpoints remain compatible.

## Risks

- Audit-backed outbox is intentionally minimal and not a replacement for real delivery history tables.
- Dedupe by audit reason is acceptable for this first safety contract but not a high-volume notification system.
- A later real delivery task needs destination config, secrets handling, retries, and provider-specific tests.
