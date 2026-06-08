# Phase 7 Slack webhook live smoke execution

## Goal

Execute exactly one Slack webhook live-smoke attempt only after `phase7-slack-webhook-live-smoke-approval` is accepted.

Current status: blocked. This task must not execute in the current turn.

## Requirements

- Execution requires prior accepted approval for exactly one attempt.
- Execution target is fixed:
  - destination id: `ops-slack-primary`
  - alert code: `stage_spool_failed_messages_present`
  - confirmation phrase: `SEND REAL OPS ALERTS`
- Execution must use the implemented gated real-send path, not an ad hoc webhook call.
- Execution must not expose `OPS_SLACK_WEBHOOK_URL`.
- Execution must record audit/history evidence and rollback verification after the attempt.
- Execution must stop after one provider call attempt, regardless of success or failure.

## Acceptance Criteria

- [x] Execution task exists and is explicitly blocked.
- [x] Preconditions and one-attempt limit are documented.
- [x] No live send was run in this setup pass.

## Notes

- Do not start or run this task until approval is accepted.
