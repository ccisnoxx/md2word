# Phase 7 Slack Webhook Live Smoke Approval Design

## Decision

Approval accepted on 2026-06-09 for exactly one future live Slack webhook smoke under the fixed contract below.

This design does not authorize sending from the approval task itself. Execution remains a separate task and must verify runtime gates immediately before any provider call.

The phrase `直接按照剩余任务清单全部开始实现` authorized task creation and planning documentation only; it did not authorize real external send. The later user approval naming `phase7-slack-webhook-live-smoke-approval` is the accepted approval gate.

## Approval Contract

The approval must include all of these facts in one operator-approved step:

- destination id: `ops-slack-primary`
- alert code: `stage_spool_failed_messages_present`
- confirmation phrase: `SEND REAL OPS ALERTS`
- maximum attempts: one
- rollback口径 accepted
- no secret value disclosure

## Hard Stops

- Missing exact destination id.
- Missing exact alert code.
- Missing exact confirmation phrase.
- Any request for multiple attempts.
- Any request to broaden destinations or alert codes.
- Any secret value exposure.
- Active kill switch, dry-run mismatch, disabled capability, missing destination config, or inactive alert code.

## Handoff

`phase7-slack-webhook-live-smoke-execution` may move from approval-blocked to execution-prepared, but execution must still be a separate step with runtime gate verification and at most one send attempt.
