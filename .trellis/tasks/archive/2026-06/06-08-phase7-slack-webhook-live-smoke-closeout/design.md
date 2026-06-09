# Phase 7 Slack Webhook Live Smoke Closeout Design

## Decision

Keep closeout blocked until a future approved live-smoke execution produces evidence.

## Evidence Required

- Execution task id and timestamp.
- Gate snapshot.
- Destination id and alert code.
- Provider-call boolean.
- Outcome and redacted provider id/request id if available.
- Audit/history query result.
- Rollback verification result.
- Statement that secret values were not exposed.

## Acceptance Outcomes

- `accepted_real_delivery_pilot`
- `failed_live_smoke`
- `blocked_before_provider_call`
- `timed_out`
- `rate_limited`
- `rolled_back`

No outcome can be assigned without execution evidence.
