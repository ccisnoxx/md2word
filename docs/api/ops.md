# Ops APIs

## Scope

`/api/v1/ops/recovery-actions` provides an Admin-only recovery action registry and exact-target preview contract.

`/api/v1/ops/alert-deliveries` provides an Admin-only fake alert delivery outbox safety contract.

These APIs do not execute real provider calls, real external alert delivery, scheduler loops, physical deletion, S3 deletion, MinerU recovery, pdf-mineru parsing, translation providers, or Word generation.

## Recovery Actions

### `GET /api/v1/ops/recovery-actions`

Returns the current recovery action registry and a safety object.

Each action includes:

- stable identity: `action_id`, `label`, `category`, `target_type`
- availability and routing: `available`, `known_gaps`, `suggested_route`
- gates: `requires_admin`, `requires_reason`, `requires_confirmation`, `dry_run_supported`
- risk flags: `mutates_metadata`, `mutates_queue`, `calls_provider`, `sends_notification`, `deletes_data`
- audit contract: `audit_action`

Candidate-only actions such as provider cancellation and automated cleanup execution are listed with `available=false` until their execution contracts are implemented and reviewed.

`alert.delivery` is available only for the local fake outbox contract. It does not send Slack/email/webhook notifications.

### `POST /api/v1/ops/recovery-actions/preview`

Request:

```json
{
  "action_id": "document_job.retry",
  "target_type": "document_job",
  "target_id": "docjob_123"
}
```

Response includes:

- `eligible`
- `missing_gates`
- safe target summary
- risk flags
- audit action
- safety metadata proving no execution or mutation occurred

Unknown actions return `404`. Mismatched `target_type` returns `400`.

## Safety Contract

The registry and preview endpoints return:

```json
{
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
```

Preview reads only metadata repositories. It does not call `stage_service`, `stage_dispatcher`, lifecycle execution services, provider clients, file delete services, or notification integrations.

## Alert Delivery Fake Outbox

### `POST /api/v1/ops/alert-deliveries/preview`

Admin-only dry-run preview for exact currently active Ops alert codes.

Request:

```json
{
  "alert_codes": ["stage_spool_failed_messages_present"],
  "channel": "local_outbox",
  "dedupe_window_minutes": 60
}
```

Rules:

- `alert_codes` must be non-empty, unique, and capped at 10.
- Each code must currently exist in `GET /api/v1/health/ops-alerts`.
- First version supports only `channel=local_outbox`.
- Preview writes no audit event and sends no external notification.

### `POST /api/v1/ops/alert-deliveries/fake-send`

Admin-only fake delivery execution. It records a local audit-backed outbox attempt but sends no external notification.

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

Fake-send requires a non-empty reason and exact confirmation phrase.

Response includes:

- `action_mode`: `dry_run` or `fake_send`
- `confirmation_phrase`
- `requested_alert_codes`
- `delivery_id`
- per-alert outcomes: `deliverable`, `fake_delivered`, or `deduped`
- compact totals
- safety metadata

The endpoint writes one audit event for a non-deduped fake delivery batch:

- `action=ops.alert_delivery_fake`
- `target_type=ops_alert_delivery`
- `target_id=<delivery_id>`

Repeated requests inside the dedupe window return `deduped` and do not write a duplicate delivery audit.

Safety metadata always reports:

```json
{
  "external_delivery_executed": false,
  "provider_calls_executed": false,
  "cleanup_executed": false,
  "delete_executed": false,
  "conversion_workflow_executed": false
}
```

The API never returns or stores webhook URLs, credentials, provider secrets, local paths, file bytes, prompt text, or full health payloads.
