# Phase 7 real S3 delete guarded rollout planning

## Goal

Plan the destructive controlled rollout for real S3 object deletion without executing any delete operation.

Current status: planning scaffold prepared, but not executable because exact bucket/key/version/sentinel values have not been supplied.

## Requirements

- Keep this task separate from Slack/webhook delivery.
- Do not run real S3 delete.
- Do not run LocalStack delete.
- Require exact target values before execution planning can be accepted:
  - storage provider
  - bucket
  - object key
  - optional version id
  - expected ETag or equivalent optimistic guard where available
  - sentinel object or test fixture identity
- Require an allowlist for exactly one target in the first manual pilot.
- Require a signed deletion plan or equivalent signed preview hash.
- Require explicit destructive confirmation phrase before any execution task:
  - proposed phrase: `DELETE EXACT S3 OBJECT`
- Require metadata mutation rule:
  - local metadata may be marked deleted only after accepted provider success or a proven idempotent already-missing result
- Require audit/history evidence and rollback/incident handling before execution.

## Acceptance Criteria

- [x] Destructive rollout planning task exists.
- [x] Exact-target requirements are documented.
- [x] Missing target values are called out as blockers.
- [x] No real S3 delete or LocalStack delete was run.
- [x] Future execution remains blocked pending planning acceptance and explicit destructive approval.

## Notes

- This task cannot be accepted as executable until the operator supplies exact target values.
