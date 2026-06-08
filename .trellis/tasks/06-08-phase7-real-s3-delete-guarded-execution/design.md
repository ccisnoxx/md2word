# Phase 7 Real S3 Delete Guarded Execution Design

## Decision

Keep real S3 delete execution blocked. Planning is not executable because exact target values are missing.

## Execution Preconditions

- Accepted destructive planning with exact target values.
- Signed deletion plan hash matches target.
- Explicit approval for exactly one target.
- Capability enabled for S3 delete.
- Kill switch inactive during execution.
- Dry-run disabled only for the approved attempt.
- Confirmation phrase `DELETE EXACT S3 OBJECT`.

## Execution Constraints

- One exact object only.
- One attempt unless a later task explicitly approves retry after evidence review.
- No scheduler path.
- No LocalStack delete.
- No prefix or batch delete.
- No local metadata mutation before provider result is accepted.

## Evidence Required

- Gate snapshot.
- Signed plan hash.
- Target bucket/key/version with redaction rules if needed.
- Provider request id if available.
- Outcome and metadata mutation result.
- Audit/history and cleanup history entries.
- Rollback verification.
