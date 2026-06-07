# Phase 5 evidence backfill provider cancellation hardening

## Goal

Backfill Phase 5 archive evidence for provider cancellation fake adapter hardening so Phase 6 provider cancellation readiness starts from an accepted non-mutating, fake-only contract.

## Requirements

- Treat this as evidence backfill for existing backend behavior.
- Confirm fake provider cancellation remains Admin-only.
- Confirm preview is metadata-only and writes no audit event.
- Confirm fake-cancel requires exact target, reason, confirmation, provider operation ID, and dedupe checks.
- Confirm fake adapter returns structured contract evidence including adapter mode, contract version, idempotency key, timeout fields, outcome, error fields, and safety booleans.
- Confirm dedupe can read structured adapter details from existing audit events.
- Confirm no real provider cancellation, provider query/download, local job mutation, queue mutation, cleanup, delete, scheduler, or conversion workflow occurs.

## Acceptance Criteria

- [x] Provider cancellation preview is Admin-only and metadata-only.
- [x] Provider cancellation fake-cancel writes at most one audit event per dedupe key/window.
- [x] Structured `provider_adapter` evidence is present on non-deduped fake-cancel audit events.
- [x] Dedupe reads structured adapter details before falling back to compact reason.
- [x] Targeted backend tests pass.
- [x] Trellis validate passes.
- [x] `git diff --check` passes.

## Notes

- This backfill resolves the Phase 6 gap-audit item for `app/domains/ops/provider_cancellation.py`.
- Real provider cancellation remains out of scope.
