# Phase 7 Slack webhook live smoke preflight

## Goal

Prepare the Phase 7 Slack webhook pilot for a future live-smoke approval by proving the target, gates, rollback, and evidence plan are fixed before any real webhook send is attempted.

This task is a preflight only. It must not send Slack/webhook traffic, resolve or print secret values, mutate external provider state, or approve live execution by itself.

## Requirements

- Confirm the preflight is scoped to the existing Phase 7 Slack pilot only:
  - destination id: `ops-slack-primary`
  - channel: `slack`
  - secret ref name: `OPS_SLACK_WEBHOOK_URL`
  - target label: `#ops-alerts-phase7-pilot`
  - allowed alert code: `stage_spool_failed_messages_present`
  - confirmation phrase: `SEND REAL OPS ALERTS`
  - dedupe window: `60` minutes
  - rate limit: `3` attempts/hour
  - timeout: `10` seconds
- Treat live execution as blocked until a separate explicit approval task or operator instruction authorizes exactly one send attempt.
- Use only non-secret configuration evidence. It is acceptable to refer to `secret_ref` names, readiness booleans, masked status, and documented runtime requirements; it is not acceptable to inspect, print, store, or copy `OPS_SLACK_WEBHOOK_URL`.
- Verify the rollback口径 before live approval:
  - set `INTEGRATION_ALERT_DELIVERY_ENABLED=false`
  - set `INTEGRATION_ALERT_DELIVERY_KILL_SWITCH=true`
  - set `INTEGRATION_ALERT_DELIVERY_DRY_RUN=true`
  - disable or remove `ops-slack-primary` from `OPS_ALERT_DESTINATIONS_JSON`
  - remove or rotate `OPS_SLACK_WEBHOOK_URL`
  - verify control-plane/destination readiness returns blocked
  - inspect audit/history after any future approved live smoke
- Keep all destructive or unrelated controlled rollouts out of scope:
  - no real provider cancellation
  - no real S3 delete
  - no LocalStack delete
  - no cleanup scheduler execute
  - no conversion main flow
- Produce a clear handoff stating whether the next task may be `phase7-slack-webhook-live-smoke-approval` or remains blocked.

## Acceptance Criteria

- [x] Preflight target values are restated exactly and match the implemented pilot acceptance.
- [x] The task states that no live Slack/webhook send was run or approved.
- [x] The task records the non-secret evidence needed before approval.
- [x] The task records hard stops that must block approval.
- [x] The task records rollback steps and post-smoke evidence requirements.
- [x] The next task is explicitly marked as blocked on separate user approval for exactly one live send.

## Notes

- This task may update Trellis and CodeStable planning/status artifacts.
- This task must not stage, commit, push, or archive unless separately requested.
