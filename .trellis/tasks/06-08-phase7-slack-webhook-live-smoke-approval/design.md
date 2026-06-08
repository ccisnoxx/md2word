# Phase 7 Slack Webhook Live Smoke Approval Design

## Decision

Keep the approval gate blocked. Approval requires a future explicit instruction that authorizes exactly one live Slack webhook smoke.

The phrase `直接按照剩余任务清单全部开始实现` authorizes task creation and planning documentation only; it does not authorize real external send.

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

Only after this approval is accepted may `phase7-slack-webhook-live-smoke-execution` move from blocked to executable.
