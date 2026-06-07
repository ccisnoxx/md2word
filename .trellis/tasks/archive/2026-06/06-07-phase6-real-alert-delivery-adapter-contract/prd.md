# Phase 6 real alert delivery adapter contract

## Goal

Fix the real alert delivery adapter contract and prove fake/local parity without sending Slack, email, or webhook messages.

## Requirements

- Add a stable Admin-only read-only contract report for future real alert delivery adapters.
- The contract must describe required idempotency, timeout, provider-result, structured-audit, secret-redaction, rate-limit, and safety fields.
- Existing fake alert delivery preview/fake-send must expose adapter evidence with the same contract version.
- Existing fake-send audit details must include the adapter evidence.
- Integration control plane may report contract/fake parity as present, but real alert delivery must remain blocked.
- Ops Dashboard should surface the adapter contract and fake parity state.
- No endpoint may call real Slack/email/webhook, resolve secret values, or send external notifications.

## Acceptance Criteria

- [ ] Admin can read the adapter contract report.
- [ ] Operator is rejected from the adapter contract endpoint.
- [ ] Contract report is read-only and reports no provider calls, external delivery, audit writes, cleanup, delete, conversion, or secret exposure.
- [ ] Fake preview/fake-send items include adapter evidence using the contract version.
- [ ] Fake-send audit details include adapter evidence and still report no external delivery or provider calls.
- [ ] Real alert delivery capability remains blocked by the integration control plane.
- [ ] Frontend displays contract/fake parity evidence.
- [ ] Targeted backend tests, OpenAPI export check, and frontend build pass.

## Notes

- This task intentionally does not implement live Slack/email/webhook sending.
