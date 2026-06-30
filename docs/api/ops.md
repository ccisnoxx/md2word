# Ops APIs

## Scope

`/api/v1/ops/recovery-actions` provides an Admin-only recovery action registry and exact-target preview contract.

`/api/v1/ops/integration-capabilities` provides an Admin-only real integration control-plane status contract.

`/api/v1/ops/alert-deliveries` provides an Admin-only fake alert delivery outbox safety contract.

`/api/v1/ops/alert-deliveries/adapter-contract` provides an Admin-only real alert delivery adapter contract and fake parity report.

`/api/v1/ops/s3-deletions/adapter-contract` provides an Admin-only S3 delete adapter contract, LocalStack profile, and file-retention fake parity report.

`/api/v1/ops/alert-destinations` provides an Admin-only alert destination configuration dry-run contract.

`/api/v1/ops/provider-cancellations` provides an Admin-only fake provider cancellation safety contract.

`/api/v1/ops/provider-cancellations/semantics-verification` provides an Admin-only read-only MinerU cancellation semantics verification report.

File retention cleanup run execution lives under `/api/v1/files/retention/cleanup-runs/*`; the Ops recovery action registry links to it as `file_retention.automated_cleanup_execute`.

Ops namespace APIs do not execute real provider calls, real external alert delivery, scheduler loops, physical deletion, S3 deletion, MinerU recovery, pdf-mineru parsing, translation providers, or Word generation. The integration control plane only reports disabled-by-default capability gates. The Files cleanup run contract may execute only guarded local physical deletion through the existing file-retention safety contract.

P2 online gate evidence is collected by `scripts/ops/run_p2_online_gate.py`. When run with
`--sync-acceptance`, the script registers the compact P2 summary in Acceptance Center as
`acceptance_p2_online_gate_current`; Acceptance Center remains an evidence index and does not execute any
ops, provider, cleanup, or conversion action.
The script accepts an admin JWT through `P2_ONLINE_BEARER_TOKEN`, an admin password through
`P2_ONLINE_PASSWORD`, or the legacy operations token through `P2_ONLINE_ADMIN_TOKEN` / `ADMIN_TOKEN`.

## Integration Control Plane

### `GET /api/v1/ops/integration-capabilities`

Returns the current real external/destructive capability status. This endpoint is Admin-only and read-only.

Capabilities:

- `alert_delivery`: real Slack/email/webhook delivery.
- `provider_cancellation`: real provider-side cancellation.
- `s3_deletion`: real S3 object deletion.
- `cleanup_scheduler_execute`: autonomous cleanup scheduler execution.
- `quota_enforcement`: upload quota enforcement.

Default behavior:

- Every real external/destructive capability is disabled or blocked by default.
- Alert delivery, provider cancellation, S3 deletion, and scheduler execution remain blocked even if their enable flag is set because the real adapters or execution loops are not implemented yet.
- S3 deletion additionally reports the LocalStack/fake parity contract version and remains blocked until a future real adapter is implemented and verified.
- Provider cancellation is also blocked because current verified public MinerU docs do not expose a provider-side cancellation endpoint or cancellation result semantics.
- Quota enforcement can become `ready` only when `FILES_QUOTA_POLICY_ENABLED=true`, `FILES_QUOTA_POLICY_DRY_RUN=false`, `FILES_QUOTA_POLICY_KILL_SWITCH=false`, quota bytes are configured, and thresholds are valid.

Each capability includes:

- `status`: `blocked`, `dry_run_only`, or `ready`.
- `real_execution_enabled`.
- `dry_run_only`.
- `kill_switch_active`.
- `configured`.
- `ready`.
- `blocking_reasons`.
- `required_gates`.
- `safe_config`.

Safety metadata always reports:

```json
{
  "read_only": true,
  "provider_calls_executed": false,
  "external_delivery_executed": false,
  "s3_delete_executed": false,
  "cleanup_scheduler_executed": false,
  "quota_enforcement_executed": false,
  "cleanup_executed": false,
  "delete_executed": false,
  "conversion_workflow_executed": false,
  "audit_events_written": false,
  "secret_values_exposed": false
}
```

The response never includes secret values, webhook URLs, provider payloads, object bodies, local filesystem paths, prompt text, or file bytes.

## S3 Delete Adapter Contract

### `GET /api/v1/ops/s3-deletions/adapter-contract`

Returns the current S3 delete adapter contract and LocalStack/fake parity evidence. This endpoint is Admin-only and read-only.

The response includes:

- `contract_version`
- fake adapter id/mode
- linked file-retention fake contract version
- LocalStack harness profile
- non-sensitive S3 storage config summary
- required request/result/audit/safety fields
- parity checks for exact bucket/key/version, idempotency, audit shape, and metadata mutation rules
- blocking reasons
- safety metadata

Default blocking reasons include:

- `real_s3_delete_adapter_not_implemented`
- `localstack_contract_not_executed_in_runtime`
- `live_s3_delete_disabled_by_default`
- `cleanup_scheduler_execute_deferred`

Safety metadata always reports:

```json
{
  "read_only": true,
  "provider_calls_executed": false,
  "real_s3_delete_executed": false,
  "localstack_calls_executed": false,
  "cleanup_executed": false,
  "scheduler_loop_executed": false,
  "delete_executed": false,
  "metadata_mutated": false,
  "audit_events_written": false,
  "conversion_workflow_executed": false,
  "secret_values_exposed": false
}
```

This endpoint does not run LocalStack, call AWS/boto3 delete APIs, execute cleanup, start a scheduler loop, mutate `document_files`, or write audit events. Existing file-retention S3 rows still return the fake retention delete contract under Files API while real S3 deletion remains unavailable.

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
- per-alert `adapter_result` using `contract_version=ops-alert-delivery-adapter-v1`
- compact totals
- safety metadata

The endpoint writes one audit event for a non-deduped fake delivery batch:

- `action=ops.alert_delivery_fake`
- `target_type=ops_alert_delivery`
- `target_id=<delivery_id>`

Repeated requests inside the dedupe window return `deduped` and do not write a duplicate delivery audit.

### `GET /api/v1/ops/alert-deliveries/adapter-contract`

Admin-only read-only report for the real Slack/email/webhook adapter contract and current fake parity.

Response includes:

- `contract_version=ops-alert-delivery-adapter-v1`
- `fake_adapter_id=local_outbox_fake`
- `fake_adapter_mode=fake`
- `real_channels`: `slack`, `email`, `webhook`
- `required_request_fields`, `required_result_fields`, `required_audit_fields`, and `required_safety_fields`
- `parity_checks` proving the fake path uses the same contract version, stable dedupe/idempotency keys, structured audit details, and no provider calls or external delivery
- destination count/channel summary from `OPS_ALERT_DESTINATIONS_JSON`, without secret values
- `blocking_reasons` showing live delivery still requires explicit real-send gates and disabled-by-default rollout controls
- read-only safety metadata

This endpoint does not resolve secret refs, send messages, call providers, write audit events, or expose webhook URLs/credentials.

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

### `POST /api/v1/ops/alert-deliveries/real-send/preview`

Admin-only Phase 7 Slack webhook pilot preview. It validates gates for exactly one destination and one alert code, but does not resolve the secret value, call Slack, send a webhook, or write audit.

Fixed pilot values:

- `destination_id=ops-slack-primary`
- `channel=slack`
- `secret_ref=OPS_SLACK_WEBHOOK_URL`
- `target_label=#ops-alerts-phase7-pilot`
- `alert_code=stage_spool_failed_messages_present`
- `confirmation_phrase=SEND REAL OPS ALERTS`
- `rate_limit_per_hour=3`
- `dedupe_window_minutes=60`
- `timeout_seconds=10`

Request:

```json
{
  "alert_codes": ["stage_spool_failed_messages_present"],
  "destination_ids": ["ops-slack-primary"],
  "dedupe_window_minutes": 60
}
```

Response uses the alert delivery response shape with:

- `action_mode=real_send_preview`
- `channel=slack`
- `requested_destination_ids=["ops-slack-primary"]`
- per-item `destination_id`, `target_label`, `missing_gates`, `idempotency_key`, and real adapter evidence
- `gate_snapshot`
- `rollback`
- safety metadata with `provider_calls_executed=false`, `external_delivery_executed=false`, `audit_events_written=false`, and `secret_values_exposed=false`

### `POST /api/v1/ops/alert-deliveries/real-send`

Admin-only Phase 7 Slack webhook pilot execution. It may call Slack only after all gates pass.

Request:

```json
{
  "alert_codes": ["stage_spool_failed_messages_present"],
  "destination_ids": ["ops-slack-primary"],
  "reason": "phase7 slack webhook delivery pilot",
  "confirmation": "SEND REAL OPS ALERTS",
  "dedupe_window_minutes": 60
}
```

Execution gates:

- `INTEGRATION_ALERT_DELIVERY_ENABLED=true`
- `INTEGRATION_ALERT_DELIVERY_DRY_RUN=false`
- `INTEGRATION_ALERT_DELIVERY_KILL_SWITCH=false`
- exact destination id `ops-slack-primary`
- exact alert code `stage_spool_failed_messages_present`
- active health ops alert
- destination config exactly matches the fixed pilot values
- `OPS_SLACK_WEBHOOK_URL` resolves to a non-empty secret value
- confirmation phrase matches `SEND REAL OPS ALERTS`
- dedupe and rate-limit gates pass

Real-send writes `action=ops.alert_delivery_real` audit for execution attempts, including blocked, sent, deduped, rate-limited, failed, and timed-out outcomes. Audit details include gate snapshot, destination id, target label, alert code, dedupe key, idempotency key, adapter result, safety, and rollback hints.

The API must not return or store the Slack webhook URL, secret value, authorization headers, Slack response body, full health payload, or provider payload.

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
    "target_label": "#ops-alerts-phase7-pilot",
    "allowlist": ["stage_spool_failed_messages_present"],
    "rate_limit_per_hour": 3,
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
- Real external delivery requires the explicit Phase 7 real-send endpoint, fixed pilot target, confirmation phrase, integration capability gates, dedupe, rate limit, and secret resolution.

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

This dry-run contract is integration readiness only. It does not send Slack/email/webhook alerts and does not create delivery history.

## Provider Cancellation Fake Contract

### `GET /api/v1/ops/provider-cancellations/semantics-verification`

Admin-only read-only verification report for MinerU provider-side cancellation semantics.

Response includes:

- `provider=mineru`
- `verification_status=verified_blocked`
- `decision=unsupported_by_public_docs`
- `public_docs_support_real_cancel=false`
- `real_provider_cancel_allowed=false`
- documented operations used by this system, such as task submission and batch result query
- documented task statuses seen in public API docs
- unsupported operation gaps, including missing cancel endpoint and missing cancel idempotency/timeout/result semantics
- source labels and URLs for primary public docs
- safety metadata proving no provider call, local mutation, queue mutation, audit write, cleanup, delete, conversion, or secret exposure

This endpoint does not call MinerU and does not change the fake cancellation execution contract.

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

This contract is intentionally not a real provider cancellation integration. Real provider cancellation remains blocked because current verified public MinerU docs do not document a cancel endpoint or safe cancellation result semantics. A future real adapter would require provider-written confirmation, timeout/error/idempotency contract, local-state transition rules, and fake-client coverage.
