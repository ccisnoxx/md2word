# Phase 7 Slack Webhook Delivery Pilot Implementation Plan

## Task Classification

Controlled external-send rollout. Current phase is planning only.

Do not implement code until this task is reviewed and moved from `planning` to `in_progress`.

## Completed Planning Work

- [x] Created Trellis child task under `06-08-phase7-controlled-real-integration-rollout-planning`.
- [x] Fixed destination, secret-ref name, allowed alert code, confirmation phrase, dedupe, rate limit, timeout, and rollback scope.
- [x] Wrote `prd.md`, `design.md`, and `implement.md`.
- [x] Curated `implement.jsonl` and `check.jsonl`.
- [x] Ran Trellis context validation.

## Fixed Values

- Destination id: `ops-slack-primary`
- Channel: `slack`
- Secret ref name: `OPS_SLACK_WEBHOOK_URL`
- Target label: `#ops-alerts-phase7-pilot`
- Allowed alert code: `stage_spool_failed_messages_present`
- Confirmation phrase: `SEND REAL OPS ALERTS`
- Dedupe window: `60` minutes
- Rate limit: `3` attempts/hour
- Timeout: `10` seconds

## Implementation Checklist

- [x] Review `prd.md` and `design.md`; get explicit approval to start implementation.
- [x] Run `task.py start` only after approval.
- [x] Load relevant Trellis/spec context before code edits.
- [x] Add or extend backend schemas for real-send preview/execution requests and responses.
- [x] Add a real Slack webhook adapter boundary that returns redacted provider results.
- [x] Add a secret resolver boundary for `OPS_SLACK_WEBHOOK_URL`; keep secret values out of responses, audit, history, logs, and frontend state.
- [x] Add exact pilot gate validation for `ops-slack-primary` and `stage_spool_failed_messages_present`.
- [x] Add capability-gate enforcement using `integration_alert_delivery_enabled`, `integration_alert_delivery_dry_run`, and `integration_alert_delivery_kill_switch`.
- [x] Add rate-limit and dedupe checks using the fixed `3/hour` and `60 minutes` pilot values.
- [x] Add real-send preview endpoint that never resolves secret values and never calls Slack.
- [x] Add real-send endpoint that calls Slack only after every gate passes and confirmation equals `SEND REAL OPS ALERTS`.
- [x] Add structured audit/history for blocked, sent, deduped, rate-limited, failed, and timed-out outcomes.
- [x] Update integration control-plane status so real alert delivery reports ready only when the real adapter and required destination gates are present.
- [x] Update Ops Dashboard with exact target, preview, gate state, confirmation phrase, rate-limit/dedupe, and rollback visibility.
- [x] Update API docs and OpenAPI.
- [x] Preserve existing fake preview/fake-send behavior and tests.

## Validation Plan

Automated validation must not send Slack/webhook network traffic.

Planning validation completed:

- `python3 ./.trellis/scripts/task.py validate 06-08-phase7-slack-webhook-delivery-pilot`
- Result: passed; `implement.jsonl` has 7 entries and `check.jsonl` has 6 entries.

- Backend tests:
  - default blocked by config
  - kill switch blocks before provider call
  - dry-run flag blocks execution
  - non-Admin receives 403
  - wrong destination id rejected
  - wrong alert code rejected
  - missing inactive alert rejected
  - wrong confirmation rejected
  - destination allowlist enforced
  - secret value is not exposed
  - preview writes no audit and makes no provider call
  - rate limit and dedupe enforced
  - success path uses a fake injected provider, not a real Slack call
  - fake-send compatibility remains intact
- API docs/OpenAPI currentness check.
- Frontend build after UI changes.
- `git diff --check`.

Validation completed:

- PASS: 10 focused backend tests for real alert delivery, adapter contract, destination dry-run, and integration control-plane behavior.
- PASS: `python3 scripts/ops/export_openapi.py --check --no-diff`.
- PASS: `npm --prefix frontend run build`.
- PASS: `git diff --check`.

Live-send status:

- Not run. No real Slack/webhook delivery was attempted.

Live-send smoke is a manual, separately approved final gate:

- exactly one destination: `ops-slack-primary`
- exactly one alert code: `stage_spool_failed_messages_present`
- exactly one confirmation phrase: `SEND REAL OPS ALERTS`
- at most one approved live attempt
- record observed audit/history result afterward

## Rollback Checklist

- [ ] Set `INTEGRATION_ALERT_DELIVERY_ENABLED=false`.
- [ ] Set `INTEGRATION_ALERT_DELIVERY_KILL_SWITCH=true`.
- [ ] Set `INTEGRATION_ALERT_DELIVERY_DRY_RUN=true`.
- [ ] Disable or remove `ops-slack-primary` in `OPS_ALERT_DESTINATIONS_JSON`.
- [ ] Remove or rotate `OPS_SLACK_WEBHOOK_URL`.
- [ ] Verify control-plane `alert_delivery` status is blocked.
- [ ] Verify destination dry-run no longer reports a ready live-send target.
- [ ] Inspect audit/history for the most recent `ops.alert_delivery_real` event.

## Guardrails

- Do not run real Slack/webhook delivery during implementation or automated tests.
- Do not run provider cancellation.
- Do not run S3 deletion.
- Do not run LocalStack deletion.
- Do not run scheduler execute.
- Do not run conversion main flow, MinerU parsing/recovery, translation provider calls, or Word generation.
- Do not stage, commit, push, branch switch, revert, or destructively clean files unless explicitly requested.

## Residual Risks

- A live smoke needs a real approved Slack webhook secret that this task must not store.
- The chosen alert code must be active in the target runtime before a live send can happen.
- Slack webhook behavior can fail outside local control; timeout/failure paths must be accepted before live send.
