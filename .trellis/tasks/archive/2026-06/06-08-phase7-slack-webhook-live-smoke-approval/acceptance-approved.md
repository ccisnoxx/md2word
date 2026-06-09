# Phase 7 Slack Webhook Live Smoke Approval Accepted

## Decision

Accepted as `approval granted for exactly one future live-smoke attempt`.

Approval date: 2026-06-09.

This acceptance does not execute the live send.

## Approved Contract

- Destination id: `ops-slack-primary`
- Channel: `slack`
- Secret ref name: `OPS_SLACK_WEBHOOK_URL`
- Target label: `#ops-alerts-phase7-pilot`
- Allowed alert code: `stage_spool_failed_messages_present`
- Confirmation phrase: `SEND REAL OPS ALERTS`
- Maximum attempts: one live send attempt
- Secret handling: no secret value may be printed, copied, stored, or exposed

## Rollback口径

- Set `INTEGRATION_ALERT_DELIVERY_ENABLED=false`.
- Set `INTEGRATION_ALERT_DELIVERY_KILL_SWITCH=true`.
- Set `INTEGRATION_ALERT_DELIVERY_DRY_RUN=true`.
- Disable or remove `ops-slack-primary` from `OPS_ALERT_DESTINATIONS_JSON`.
- Remove or rotate `OPS_SLACK_WEBHOOK_URL`.
- Verify control-plane/destination readiness returns blocked.
- Inspect audit/history after any future approved live smoke.

## Execution Handoff

`phase7-slack-webhook-live-smoke-execution` may proceed only as a separate step. Before any provider call, it must verify runtime gates, active alert state, exact target, confirmation phrase, one-attempt limit, and secret redaction.

## Safety Statement

This approval acceptance did not run Slack/webhook live send, inspect or expose `OPS_SLACK_WEBHOOK_URL`, run provider cancellation, run S3 delete, run LocalStack delete, run cleanup scheduler execute, run conversion main flow, stage files, commit, push, archive, or destructively clean files.
