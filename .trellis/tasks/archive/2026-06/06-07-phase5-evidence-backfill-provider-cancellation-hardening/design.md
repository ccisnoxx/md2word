# Phase 5 Provider Cancellation Hardening Evidence Backfill Design

## Decision

Accept the current fake provider cancellation adapter hardening as Phase 5 evidence.

The accepted contract is fake-only:

- `provider=mineru` is the only supported provider value.
- The target must be exact: `document_job` or `legacy_job` plus target ID.
- Preview reads persisted metadata only.
- Fake-cancel records audit only when the target is eligible and not deduped.
- The fake adapter returns stable structured evidence instead of calling a real provider.

## Evidence Surface

- `app/domains/ops/provider_cancellation.py`
  - Defines `OpsProviderCancellationFakeAdapter`.
  - Emits `contract_version=provider-cancel-fake-v1`.
  - Emits `adapter_mode=fake`.
  - Carries idempotency key, timeout fields, outcome, nullable error fields, and safety booleans.
  - Reads dedupe keys from structured audit details and then compact reason for compatibility.
- `app/domains/ops/router.py`
  - Writes `ops.provider_cancellation_fake` audit details only for non-deduped fake-cancel.
  - Maps API safety booleans without exposing provider payloads or credentials.
- `tests/test_fastapi_jobs_backend.py`
  - Covers preview, fake-cancel, dedupe, gates, registry, and no provider/client mutation.

## Safety Boundary

This evidence explicitly does not enable:

- real provider cancellation;
- MinerU recovery query/download;
- local job cancellation or queue mutation;
- cleanup execution, physical deletion, S3 deletion, or scheduler loops;
- pdf-mineru parsing, translation provider calls, or Word generation.

## Phase 6 Dependency

Phase 6 real provider cancellation must still verify primary provider semantics before implementing any real adapter. This Phase 5 evidence only proves the fake adapter baseline.
