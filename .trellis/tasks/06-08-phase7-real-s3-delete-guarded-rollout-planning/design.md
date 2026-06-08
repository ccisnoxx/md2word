# Phase 7 Real S3 Delete Guarded Rollout Planning Design

## Decision

Prepare the destructive rollout design but keep execution blocked. The missing exact target values are intentional blockers.

## Target Contract

The first pilot must target exactly one object:

- storage provider: `s3`
- bucket: pending operator input
- object key: pending operator input
- version id: pending operator input or explicit `null`
- expected ETag: pending operator input or explicit unavailable reason
- sentinel/test object identity: pending operator input

No prefix-wide, bucket-wide, delete-all, batch, or scheduler-driven delete is allowed in the first pilot.

## Gate Contract

- Capability flag must be enabled only for the delete lane.
- Kill switch must be off for execution and verified on rollback.
- Dry-run/preview must remain the default operator path.
- Signed plan hash must match the exact target.
- Confirmation phrase must match `DELETE EXACT S3 OBJECT`.
- Admin/operator role must be enforced.
- Idempotency key must be stable for the exact bucket/key/version/plan hash.

## Result Contract

Allowed outcomes:

- `deleted`
- `already_missing`
- `version_mismatch`
- `failed`
- `timed_out`
- `blocked`

Metadata mutation is allowed only for `deleted` or approved idempotent `already_missing`.

## Rollback And Incident Handling

- Stop further deletes by disabling the S3 delete capability.
- Activate the S3 delete kill switch.
- Restore dry-run-only behavior.
- Remove target allowlist entry.
- Inspect audit/history and cleanup history.
- If provider deletion succeeded but metadata mutation failed, reconcile metadata manually from audit evidence.
- If provider timeout occurred, treat state as unknown until object existence is verified by a separate approved read-only check.

## Blockers

- Exact bucket/key/version/sentinel values are missing.
- No signed plan hash exists for the target.
- No destructive execution approval exists.
