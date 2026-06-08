# Phase 7 Slack Webhook Live Smoke Execution Design

## Decision

Keep execution blocked until explicit approval exists. The only executable form is the product real-send endpoint with all gates passing and exactly one send attempt.

## Execution Preconditions

- `phase7-slack-webhook-live-smoke-preflight` accepted.
- `phase7-slack-webhook-live-smoke-approval` accepted.
- `OPS_SLACK_WEBHOOK_URL` configured by operator but not exposed.
- `OPS_ALERT_DESTINATIONS_JSON` contains the exact `ops-slack-primary` config.
- `INTEGRATION_ALERT_DELIVERY_ENABLED=true`.
- `INTEGRATION_ALERT_DELIVERY_DRY_RUN=false`.
- `INTEGRATION_ALERT_DELIVERY_KILL_SWITCH=false`.
- `stage_spool_failed_messages_present` is active.

## Execution Constraints

- One attempt maximum.
- No retry loop.
- No alternate destination.
- No additional alert codes.
- No direct `curl` to Slack/webhook URL.
- No secret value in response, audit, docs, logs, shell output, or frontend state.

## Evidence Required After Future Execution

- Request metadata excluding secrets.
- Gate snapshot.
- Outcome: `sent`, `failed`, `timed_out`, `deduped`, `rate_limited`, or `blocked`.
- Provider-call boolean.
- Redacted external message id or request id where available.
- Audit/history lookup evidence.
- Rollback verification.
