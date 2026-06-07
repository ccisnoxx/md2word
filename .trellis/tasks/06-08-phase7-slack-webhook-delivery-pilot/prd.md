# Phase 7 Slack webhook delivery pilot

## Goal

Implement Phase 7's first controlled real integration closed loop: one Slack webhook delivery pilot for one approved destination, one allowed alert code, and one explicit confirmation phrase.

This task is currently in planning. Code implementation must not start until `prd.md`, `design.md`, and `implement.md` are reviewed and the task is explicitly started.

## Fixed Pilot Parameters

These values are fixed for the first implementation pass:

| Field | Value |
| --- | --- |
| Destination id | `ops-slack-primary` |
| Channel | `slack` |
| Secret ref name | `OPS_SLACK_WEBHOOK_URL` |
| Target label | `#ops-alerts-phase7-pilot` |
| Allowed alert code | `stage_spool_failed_messages_present` |
| Confirmation phrase | `SEND REAL OPS ALERTS` |
| Dedupe window | `60` minutes |
| Rate limit | `3` attempts per hour for this destination |
| Provider timeout | `10` seconds |
| Initial live-send scope | At most one approved live-send smoke after separate explicit approval |

The secret value for `OPS_SLACK_WEBHOOK_URL` must never be committed, printed, returned in an API response, stored in audit details/history, or rendered in the frontend.

## Requirements

- Add the minimum backend support for a real Slack webhook delivery adapter while preserving the existing fake/local outbox behavior.
- Keep real alert delivery disabled by default through the existing integration control plane.
- Require Admin role for real-send preview and execution.
- Require exact target selection:
  - `destination_ids` must be exactly `["ops-slack-primary"]`.
  - `alert_codes` must be exactly `["stage_spool_failed_messages_present"]` for the pilot.
  - No implicit all-alert delivery and no broad destination selection.
- Resolve only the configured secret reference `OPS_SLACK_WEBHOOK_URL` at execution time; do not expose its value.
- Add a real-send endpoint or mode that is distinct from fake-send in action mode, audit action, confirmation phrase, and adapter result.
- Preserve dry-run/preview before live send.
- Enforce destination allowlist, enabled flag, secret-ref presence, target label, rate limit, dedupe window, idempotency key, provider timeout, capability flag, dry-run flag, and kill switch before any network call.
- Write structured audit details and delivery history for real-send attempts, including blocked, sent, deduped, failed, and timed-out outcomes.
- Store only non-sensitive provider metadata, such as status/outcome and a non-sensitive provider request id if available. Do not store Slack response body, webhook URL, authorization headers, or payload containing secrets.
- Update Ops Dashboard to clearly display the exact destination, alert code, confirmation phrase, gate status, kill-switch state, and rollback state before real send is reachable.
- Update API docs and OpenAPI for the new real-send surface.
- Add focused backend/frontend tests that prove default blocked behavior, dry-run safety, exact target validation, secret redaction, rate limit/dedupe, kill-switch blocking, audit details, and fake behavior compatibility.
- Real live-send smoke is not part of normal automated tests. It requires a separate explicit user approval after implementation tests pass.

## Rollback Plan

Rollback must be executable without code revert:

1. Set `INTEGRATION_ALERT_DELIVERY_ENABLED=false`.
2. Set `INTEGRATION_ALERT_DELIVERY_KILL_SWITCH=true`.
3. Set `INTEGRATION_ALERT_DELIVERY_DRY_RUN=true`.
4. Disable or remove `ops-slack-primary` from `OPS_ALERT_DESTINATIONS_JSON`.
5. Remove or rotate the secret behind `OPS_SLACK_WEBHOOK_URL`.
6. Verify `/api/v1/ops/integration-capabilities` reports `alert_delivery` as blocked.
7. Verify alert destination dry-run no longer reports a live-send-ready destination.
8. Inspect audit/history for the last real-send attempt and confirm no retries are still pending.

## Inputs Reviewed

- Parent planning task: `.trellis/tasks/06-08-phase7-controlled-real-integration-rollout-planning/`
- Phase 6 alert delivery adapter contract: `.trellis/tasks/archive/2026-06/06-07-phase6-real-alert-delivery-adapter-contract/`
- Current alert delivery fake service, destination dry-run service, adapter contract, and integration control plane.

## Acceptance Criteria

- [x] Real Slack webhook delivery remains blocked by default in config and control-plane status.
- [x] Only Admin can access real-send preview/execution surfaces.
- [x] The pilot accepts only destination `ops-slack-primary` and alert code `stage_spool_failed_messages_present`.
- [x] The confirmation phrase for real send is exactly `SEND REAL OPS ALERTS`.
- [x] `OPS_SLACK_WEBHOOK_URL` is resolved only during approved execution and is never exposed in API response, audit details, history, logs, frontend state, or tests.
- [x] Rate limit is enforced at `3` attempts per hour for `ops-slack-primary`.
- [x] Dedupe window is enforced at `60` minutes with a stable idempotency key.
- [x] Kill switch blocks execution before any provider call.
- [x] Dry-run/preview validates gates without executing external delivery or writing audit.
- [x] Real-send attempts write structured audit/history with redacted provider metadata.
- [x] Existing fake-send preview and fake-send behavior remain compatible.
- [x] Frontend displays exact target, gate state, confirmation phrase, and rollback state.
- [x] API docs and OpenAPI are updated.
- [x] Focused tests pass without real Slack/webhook network calls.
- [x] Any live-send smoke is performed only after separate explicit approval and is limited to one approved attempt.

## Notes

- The chosen alert code is existing critical health warning `stage_spool_failed_messages_present`. A live send can proceed only when that alert is active in the target runtime; do not manipulate conversion workflows or stage spool state solely to activate it without separate approval.
- This task must not touch S3 delete, cleanup scheduler execute, provider cancellation, conversion main flow, or LocalStack.
