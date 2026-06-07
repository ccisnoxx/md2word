# Phase 7 Slack Webhook Delivery Pilot Design

## Decision

Implement the first Phase 7 controlled rollout as a Slack webhook pilot using the fixed target below:

```yaml
destination_id: ops-slack-primary
channel: slack
secret_ref: OPS_SLACK_WEBHOOK_URL
target_label: "#ops-alerts-phase7-pilot"
allowlist:
  - stage_spool_failed_messages_present
rate_limit_per_hour: 3
dedupe_window_minutes: 60
confirmation_phrase: SEND REAL OPS ALERTS
provider_timeout_seconds: 10
```

This pilot must remain independent from S3 deletion, cleanup scheduler execute, and provider cancellation.

## Current Baseline

Phase 6 completed:

- `integration-control-plane`
- `real-alert-delivery-adapter-contract`
- fake/local alert delivery parity
- alert destination dry-run with `destination_id`, `channel`, `enabled`, `secret_ref`, `target_label`, `allowlist`, `rate_limit_per_hour`, and `dedupe_window_minutes`

Current blocking reason still includes `real_alert_delivery_adapter_not_implemented`. Phase 7 should remove that reason only when the real Slack adapter, secret resolver boundary, exact-target gates, audit/history, and UI/API evidence are implemented and tested.

## API Shape

Add a real-send surface that is explicit and not confused with fake-send:

```text
POST /api/v1/ops/alert-deliveries/real-send/preview
POST /api/v1/ops/alert-deliveries/real-send
```

Preview request:

```json
{
  "alert_codes": ["stage_spool_failed_messages_present"],
  "destination_ids": ["ops-slack-primary"],
  "dedupe_window_minutes": 60
}
```

Execution request:

```json
{
  "alert_codes": ["stage_spool_failed_messages_present"],
  "destination_ids": ["ops-slack-primary"],
  "reason": "phase7 slack webhook delivery pilot",
  "confirmation": "SEND REAL OPS ALERTS",
  "dedupe_window_minutes": 60
}
```

Response should reuse the alert delivery report shape where practical but must distinguish:

- `action_mode="real_send_preview"` or `action_mode="real_send"`
- `channel="slack"`
- `destination_id="ops-slack-primary"`
- `confirmation_phrase="SEND REAL OPS ALERTS"`
- `adapter_result.adapter_mode="real"`
- `provider_calls_executed`
- `external_delivery_executed`
- `secret_values_exposed=false`

## Gate Order

The service must check gates in this order before any network call:

1. Admin authorization.
2. Capability gate:
   - `integration_alert_delivery_enabled=true`
   - `integration_alert_delivery_dry_run=false`
   - `integration_alert_delivery_kill_switch=false`
3. Request exactness:
   - one destination id, exactly `ops-slack-primary`
   - one alert code, exactly `stage_spool_failed_messages_present`
4. Active alert check against current health ops alerts.
5. Destination config:
   - destination exists
   - `channel="slack"`
   - `enabled=true`
   - `secret_ref="OPS_SLACK_WEBHOOK_URL"`
   - `target_label="#ops-alerts-phase7-pilot"`
   - allowlist contains the requested alert code
   - `rate_limit_per_hour=3`
   - `dedupe_window_minutes=60`
6. Secret ref resolves to a non-empty value without exposing it.
7. Confirmation phrase equals `SEND REAL OPS ALERTS`.
8. Dedupe and idempotency do not indicate an already-sent attempt inside 60 minutes.
9. Rate limit allows the attempt.
10. Adapter timeout is bounded to 10 seconds.

Preview stops before secret-value resolution and provider call. Execution may resolve the secret only after all non-secret gates pass.

## Adapter Boundary

Introduce a real adapter behind a small boundary:

```python
class AlertDeliveryProvider(Protocol):
    def send(self, attempt: AlertDeliveryAttempt) -> AlertDeliveryProviderResult: ...
```

The Slack webhook adapter should accept only a prepared attempt with a resolved webhook URL and a redacted-safe payload. It must return a result that does not include the webhook URL or Slack response body.

Result outcomes:

- `sent`
- `deduped`
- `blocked`
- `rate_limited`
- `failed`
- `timed_out`

Provider result fields:

- `contract_version`
- `adapter_id`
- `adapter_mode`
- `destination_id`
- `channel`
- `alert_code`
- `operation_id`
- `idempotency_key`
- `dedupe_key`
- `timeout_seconds`
- `outcome`
- `provider_request_id`
- `error_code`
- `retryable`
- `provider_calls_executed`
- `external_delivery_executed`
- `secret_values_exposed=false`

## Audit And History

Use a distinct audit action, for example:

```text
ops.alert_delivery_real
```

Audit/history details must include:

- gate snapshot
- destination id
- channel
- target label
- alert code
- dedupe key
- idempotency key
- rate-limit state
- timeout seconds
- adapter result
- provider call boolean
- external delivery boolean
- rollback hints

Audit/history details must not include:

- `OPS_SLACK_WEBHOOK_URL` value
- Slack webhook URL
- authorization headers
- Slack response body
- full health payload
- secret-bearing payload fields

## Frontend UX

Ops Dashboard should add a clearly gated real-send panel or mode:

- exact destination id and target label
- exact alert code
- dry-run/preview result
- current control-plane gate state
- confirmation phrase
- kill switch state
- rate limit and dedupe window
- rollback checklist

The real-send button must stay disabled unless preview passes, confirmation matches, and the backend reports all gates ready.

## Rollback

Operational rollback is config-first:

1. `INTEGRATION_ALERT_DELIVERY_ENABLED=false`
2. `INTEGRATION_ALERT_DELIVERY_KILL_SWITCH=true`
3. `INTEGRATION_ALERT_DELIVERY_DRY_RUN=true`
4. Disable or remove `ops-slack-primary` from `OPS_ALERT_DESTINATIONS_JSON`
5. Remove or rotate the secret behind `OPS_SLACK_WEBHOOK_URL`
6. Confirm control-plane blocked status
7. Inspect audit/history for the last real-send attempt

No code revert should be required for ordinary rollback.

## Non-Scope

- No email or generic webhook pilot.
- No multiple destinations.
- No broad alert selection.
- No provider cancellation.
- No S3 deletion.
- No cleanup scheduler execute.
- No conversion main-flow run.
- No live Slack send during automated validation.
