# Phase 7 Slack Webhook Live Smoke Preflight Implementation Plan

## Task Classification

Preflight/design/acceptance only. No live Slack/webhook send is allowed in this task.

## Implementation Checklist

- [x] Create Trellis child task `phase7-slack-webhook-live-smoke-preflight`.
- [x] Read Phase 7 planning and Slack pilot no-live acceptance.
- [x] Write PRD with exact preflight requirements and acceptance criteria.
- [x] Write design with preflight matrix, hard stops, approval handoff, and rollback口径.
- [x] Start the Trellis task after planning artifacts exist.
- [x] Write preflight acceptance that marks the task complete as no-live preflight only.
- [x] Sync Phase 7 status so the next live-smoke approval task remains blocked.
- [x] Run Trellis validation.
- [x] Confirm git status; do not stage or commit.

## Validation Plan

Allowed validation:

- `python3 ./.trellis/scripts/task.py validate 06-08-phase7-slack-webhook-live-smoke-preflight`
- `git status --short`
- Static reading of existing Trellis/CodeStable docs.

Forbidden validation:

- Real Slack/webhook send.
- Calling the real-send execution endpoint.
- Reading or printing `OPS_SLACK_WEBHOOK_URL`.
- Provider cancellation.
- S3 delete or LocalStack delete.
- Cleanup scheduler execute.
- Conversion main flow, MinerU parsing/recovery, translation provider calls, or Word generation.

## Completion Criteria

This task is complete when:

- Acceptance says `preflight completed with no live send`.
- Next task is explicitly `phase7-slack-webhook-live-smoke-approval`, blocked on separate approval.
- Hard stops and rollback口径 are recorded.
- Trellis validation passes.
- No git stage/commit/push was performed.

## Validation Completed

- PASS: `python3 ./.trellis/scripts/task.py validate 06-08-phase7-slack-webhook-live-smoke-preflight`
  - `implement.jsonl`: 6 entries
  - `check.jsonl`: 6 entries
- PASS: `python3 ./.trellis/scripts/task.py validate 06-08-phase7-controlled-real-integration-rollout-planning`
  - `implement.jsonl`: 6 entries
  - `check.jsonl`: 6 entries
- Observed `git status --short`; no staging or commit was performed.
