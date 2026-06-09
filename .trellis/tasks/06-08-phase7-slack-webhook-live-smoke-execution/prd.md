# Phase 7 Slack webhook live smoke execution

## Goal

Execute exactly one Slack webhook live-smoke attempt only after `phase7-slack-webhook-live-smoke-approval` is accepted and runtime gates pass.

Current status: approval accepted; execution entered; runtime gate verification blocked before provider call. No live send attempt has been consumed.

## Requirements

- Execution requires prior accepted approval for exactly one attempt.
- Execution target is fixed:
  - destination id: `ops-slack-primary`
  - alert code: `stage_spool_failed_messages_present`
  - confirmation phrase: `SEND REAL OPS ALERTS`
- Execution must use the implemented gated real-send path, not an ad hoc webhook call.
- Execution must not expose `OPS_SLACK_WEBHOOK_URL`.
- Execution must record audit/history evidence and rollback verification after the attempt, or record pre-provider-call gate failure evidence if gates do not pass.
- Execution must stop after one provider call attempt, regardless of success or failure.

## Acceptance Criteria

- [x] Execution task exists.
- [x] Preconditions and one-attempt limit are documented.
- [x] Approval acceptance is recorded.
- [x] Runtime gate verification was run before provider call.
- [x] Gate failure was recorded without consuming the approved live-smoke attempt.
- [ ] Exactly one live send attempt is executed only after every runtime gate passes.

## Notes

- Do not run this task without immediate runtime gate verification and the exact confirmation phrase.
