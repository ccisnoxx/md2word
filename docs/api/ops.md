# Ops APIs

## Scope

`/api/v1/ops/recovery-actions` provides an Admin-only recovery action registry and exact-target preview contract.

`/api/v1/ops/alert-deliveries` provides an Admin-only fake alert delivery outbox safety contract.

`/api/v1/ops/alert-destinations` provides an Admin-only alert destination configuration dry-run contract.

`/api/v1/ops/provider-cancellations` provides an Admin-only fake provider cancellation safety contract.

File retention cleanup run execution lives under `/api/v1/files/retention/cleanup-runs/*`; the Ops recovery action registry links to it as `file_retention.automated_cleanup_execute`.

Ops namespace APIs do not execute real provider calls, real external alert delivery, scheduler loops, physical deletion, S3 deletion, MinerU recovery, pdf-mineru parsing, translation providers, or Word generation. The Files cleanup run contract may execute only guarded local physical deletion through the existing file-retention safety contract.

## Recovery Actions

### `GET /api/v1/ops/recovery-actions`

Returns the current recovery action registry and a safety object.

Each action includes:

- stable identity: `action_id`, `label`, `category`, `target_type`
- availability and routing: `available`, `known_gaps`, `suggested_route`
- gates: `requires_admin`, `requires_reason`, `requires_confirmation`, `dry_run_supported`
- risk flags: `mutates_metadata`, `mutates_queue`, `calls_provider`, `sends_notification`, `deletes_data`
- audit contract: `audit_action`

Candidate-only execution actions are listed with `available=false` until their execution contracts are implemented and reviewed.

`alert.delivery` is available only for the local fake outbox contract. It does not send Slack/email/webhook notifications.

`provider.cancel` is available only for the fake provider cancellation contract. It does not call MinerU or any real provider cancellation API.

`file_retention.automated_cleanup_execute` is available only for the manual cleanup run execution contract under Files API. It does not start a scheduler loop or autonomous policy executor.

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

## Alert Destination Config Dry Run

### Configuration

Alert destination dry-run reads `OPS_ALERT_DESTINATIONS_JSON`.

Default:

```json
[]
```

Configured value is a JSON array:

```json
[
  {
    "destination_id": "ops-slack-primary",
    "channel": "slack",
    "enabled": false,
    "secret_ref": "OPS_SLACK_WEBHOOK_URL",
    "target_label": "#ops-alerts",
    "allowlist": ["stage_spool_failed_messages_present"],
    "rate_limit_per_hour": 30,
    "dedupe_window_minutes": 60
  }
]
```

Supported `channel` values:

- `slack`
- `email`
- `webhook`

`secret_ref` is a secret reference name only. The API does not read or return secret values.

### `POST /api/v1/ops/alert-destinations/dry-run`

Admin-only read-only dry-run for staged alert destination config.

Request:

```json
{
  "alert_codes": ["stage_spool_failed_messages_present"],
  "destination_ids": ["ops-slack-primary"]
}
```

Rules:

- `alert_codes` is optional; when present, every code must be exact, active in `GET /api/v1/health/ops-alerts`, unique, non-blank, and capped at 10.
- `destination_ids` is optional; omitted means all configured destinations.
- Empty destination config is valid and returns zero destinations.
- Invalid destination config is reported in `config_errors` and does not trigger external side effects.
- Empty destination `allowlist` blocks all requested alert codes.
- Real external delivery is still not implemented even when a destination has `enabled=true`.

Response includes:

- `configured_count`
- `selected_count`
- `config_errors`
- per-destination `status`, `missing_gates`, `matched_alert_codes`, and `blocked_alert_codes`
- safety metadata

Safety metadata always reports:

```json
{
  "read_only": true,
  "external_delivery_executed": false,
  "provider_calls_executed": false,
  "cleanup_executed": false,
  "delete_executed": false,
  "conversion_workflow_executed": false,
  "audit_events_written": false,
  "secret_values_exposed": false
}
```

This contract is integration readiness only. It does not send Slack/email/webhook alerts and does not create delivery history.

## Provider Cancellation Fake Contract

### `POST /api/v1/ops/provider-cancellations/preview`

Admin-only preview for a precise job target. It reads metadata only and does not call a provider.

Request:

```json
{
  "target_type": "document_job",
  "target_id": "docjob_123",
  "provider": "mineru",
  "dedupe_window_minutes": 60
}
```

First version supports:

- `target_type=document_job`
- `target_type=legacy_job`
- `provider=mineru`

Preview returns:

- safe target summary
- provider operation summary, based on stored MinerU IDs
- `eligible`
- `missing_gates`
- `outcome=cancelable` or `ineligible`
- safety metadata showing no provider call, no local job mutation, and no audit write

### `POST /api/v1/ops/provider-cancellations/fake-cancel`

Admin-only fake provider cancellation execution. It records a local audit-backed cancellation attempt but does not call MinerU or mutate local job state.

Request:

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

Fake-cancel requires:

- exact target type and ID
- non-empty reason
- exact confirmation phrase
- stored provider operation ID, for example MinerU batch ID

The endpoint writes one audit event for a non-deduped eligible fake cancellation:

- `action=ops.provider_cancellation_fake`
- `target_type=provider_operation`
- `target_id=<provider>:<target_type>:<target_id>`

Repeated requests inside the dedupe window return `outcome=deduped` and do not write a duplicate audit event.

Safety metadata always reports:

```json
{
  "real_provider_cancel_executed": false,
  "provider_calls_executed": false,
  "local_job_mutated": false,
  "queue_mutated": false,
  "cleanup_executed": false,
  "delete_executed": false,
  "conversion_workflow_executed": false
}
```

This contract is intentionally not a real provider cancellation integration. Real provider cancellation requires a future provider-specific task with verified API semantics, timeout/error behavior, and fake-client test coverage.
