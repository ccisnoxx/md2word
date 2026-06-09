# Phase 7 Slack webhook live smoke approval

## Goal

Capture a future explicit operator approval for exactly one Phase 7 Slack webhook live-smoke attempt.

This task is an approval gate only. The 2026-06-09 user message approving `phase7-slack-webhook-live-smoke-approval` is accepted as approval for exactly one future live-smoke execution under the fixed target below.

This approval does not execute the live send by itself.

## Requirements

- Approval must restate the fixed target:
  - destination id: `ops-slack-primary`
  - channel: `slack`
  - secret ref name: `OPS_SLACK_WEBHOOK_URL`
  - target label: `#ops-alerts-phase7-pilot`
  - allowed alert code: `stage_spool_failed_messages_present`
  - confirmation phrase: `SEND REAL OPS ALERTS`
  - at most one live send attempt
- Approval must confirm no secret value is printed, copied, stored, or exposed.
- Approval must confirm rollback口径 is understood:
  - disable `INTEGRATION_ALERT_DELIVERY_ENABLED`
  - enable `INTEGRATION_ALERT_DELIVERY_KILL_SWITCH`
  - restore `INTEGRATION_ALERT_DELIVERY_DRY_RUN=true`
  - remove/disable `ops-slack-primary`
  - remove or rotate `OPS_SLACK_WEBHOOK_URL`
- Approval must be separate from implementation, preflight, and task creation.
- If any target value changes, approval is invalid and a new preflight is required.

## Acceptance Criteria

- [x] Approval task exists.
- [x] The earlier task-list implementation request is recorded as not approving live send.
- [x] Required approval wording and fixed target values are documented.
- [x] 2026-06-09 approval is recorded for exactly one future live-smoke attempt.
- [x] Live execution still requires a separate execution step and runtime gate checks.

## Notes

- Do not run execution from this approval task.
- Do not stage, commit, push, archive, or send Slack/webhook traffic in this approval task.
