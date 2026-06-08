# Phase 7 Slack Webhook Live Smoke Preflight Design

## Decision

Run only a no-live-send preflight for the existing Slack webhook pilot. The preflight produces approval-readiness evidence, not an external delivery event.

The next live task remains blocked until the user explicitly approves exactly one real send attempt.

## Boundary

In scope:

- Confirm the fixed pilot target and allowed alert code.
- Confirm the non-secret runtime gates that must be true before approval.
- Confirm hard stops that block approval.
- Confirm rollback and post-smoke evidence requirements.
- Update planning/status artifacts so Phase 7 progression is explicit.

Out of scope:

- Calling the real-send execution endpoint.
- Calling Slack/webhook or any external provider.
- Resolving, printing, storing, or validating the value of `OPS_SLACK_WEBHOOK_URL`.
- Running provider cancellation, S3 delete, LocalStack delete, scheduler execute, or conversion main flow.
- Broadening the pilot to email, generic webhook destinations, multiple destinations, or multiple alert codes.

## Preflight Matrix

| Check | Expected Value | Evidence Type | Hard Stop |
| --- | --- | --- | --- |
| Destination id | `ops-slack-primary` | Docs/config structure only | Any other destination id |
| Channel | `slack` | Docs/config structure only | `email`, generic `webhook`, or multiple channels |
| Secret ref | `OPS_SLACK_WEBHOOK_URL` | Secret-ref name only | Secret value appears in docs, API response, audit, logs, or frontend state |
| Target label | `#ops-alerts-phase7-pilot` | Non-secret label | Any broad production channel without separate approval |
| Alert code | `stage_spool_failed_messages_present` | Active alert readiness before live approval | Any extra or inactive alert code |
| Confirmation phrase | `SEND REAL OPS ALERTS` | Operator-entered phrase at execution time | Missing or mismatched phrase |
| Dedupe window | `60` minutes | Implementation acceptance | Missing dedupe |
| Rate limit | `3` attempts/hour | Implementation acceptance | Unbounded manual retry |
| Timeout | `10` seconds | Implementation acceptance | Unbounded provider call |
| Integration flag | `INTEGRATION_ALERT_DELIVERY_ENABLED=true` before live approval | Non-secret runtime config summary | Disabled |
| Dry-run flag | `INTEGRATION_ALERT_DELIVERY_DRY_RUN=false` before live approval | Non-secret runtime config summary | Dry-run remains true for execution |
| Kill switch | `INTEGRATION_ALERT_DELIVERY_KILL_SWITCH=false` before live approval | Non-secret runtime config summary | Kill switch active |

## Approval Handoff

The preflight can hand off to `phase7-slack-webhook-live-smoke-approval` only when:

- This task acceptance is complete.
- The operator confirms the non-secret runtime config matches the matrix.
- No secret value has been exposed.
- The alert code is currently active in the target runtime.
- The user explicitly approves exactly one live send attempt.

Without that approval, live smoke remains blocked.

## Rollback口径

Rollback is config-first:

1. Set `INTEGRATION_ALERT_DELIVERY_ENABLED=false`.
2. Set `INTEGRATION_ALERT_DELIVERY_KILL_SWITCH=true`.
3. Set `INTEGRATION_ALERT_DELIVERY_DRY_RUN=true`.
4. Disable or remove `ops-slack-primary` in `OPS_ALERT_DESTINATIONS_JSON`.
5. Remove or rotate `OPS_SLACK_WEBHOOK_URL`.
6. Verify control-plane `alert_delivery` reports blocked.
7. Verify destination dry-run no longer reports a ready live-send target.
8. Inspect `ops.alert_delivery_real` audit/history after any future approved live smoke.

## Future Blocked Tasks

- `phase7-slack-webhook-live-smoke-approval`: blocked until user explicitly approves exactly one live send.
- `phase7-slack-webhook-live-smoke-execution`: blocked until approval is complete; may attempt at most one send.
- `phase7-real-s3-delete-guarded-rollout-planning`: separate destructive planning task; no execution in Slack lane.
- `phase7-cleanup-scheduler-controlled-execute-planning`: blocked until accepted real S3 delete evidence exists.
- `phase7-provider-cancellation-evidence-watch`: blocked unless provider evidence changes.
