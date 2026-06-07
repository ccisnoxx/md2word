# Phase 6 provider cancellation semantics verification

## Goal

Verify provider-side cancellation semantics for MinerU and make the result visible as read-only ops evidence before any real cancellation adapter is considered.

## Requirements

- Add an Admin-only read-only endpoint for provider cancellation semantics verification.
- The report must state whether real MinerU cancellation is currently supported by verified public/API docs.
- The report must preserve source URLs and non-sensitive evidence summaries.
- Integration control plane must reflect the verification result while keeping real provider cancellation blocked.
- Ops Dashboard must show the semantics verification result near the provider fake cancellation panel.
- No endpoint may call MinerU, mutate local jobs/queues, cancel provider work, write audit events, or expose secrets.

## Acceptance Criteria

- [ ] Admin can read the semantics verification report.
- [ ] Operator is rejected.
- [ ] Report states real provider cancellation is not enabled and not supported by current verified public docs.
- [ ] Safety flags prove no provider calls, local mutation, queue mutation, cleanup, delete, conversion, audit write, or secret exposure.
- [ ] Integration control plane no longer labels semantics as unverified; it reports unsupported-by-public-docs and remains blocked.
- [ ] Frontend displays decision, provider, support status, source count, safety flags, and blocking reasons.
- [ ] Targeted backend tests, OpenAPI export check, and frontend build pass.

## Notes

- This task does not implement real provider cancellation and must not call MinerU.
