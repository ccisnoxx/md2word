# Phase 5 Quota Enforcement Evidence Backfill Design

## Decision

Accept the current quota ready-state upload blocking and Admin override behavior as Phase 5 evidence.

The accepted behavior is configuration-gated:

- Policy disabled or dry-run: upload authorization behavior is unchanged.
- Policy enabled, configured, not dry-run, and status `ready`: projected usage reaching the block threshold blocks upload authorization.
- Admin override can allow a ready-policy block only with an override reason and exact confirmation phrase.
- Block and override events write structured audit details for replay.

## Evidence Surface

- `app/domains/files/quota_policy.py`
  - Normalizes settings into policy status.
  - Computes usage from non-deleted `document_files` metadata.
  - Evaluates dry-run and ready enforcement decisions.
  - Builds compact audit reasons for block/override.
- `app/domains/files/router.py`
  - Runs quota preflight before creating upload authorization.
  - Writes `file.quota_policy_block` or `file.quota_policy_override` structured audit details.
  - Raises `409 conflict` before upload metadata creation when blocked.
- `tests/test_fastapi_jobs_backend.py`
  - Covers dry-run no side effects, dry-run no upload blocking, ready upload block, and Admin override.
- `docs/api/files.md`
  - Documents override fields, ready block behavior, and dry-run/readiness boundaries.

## Rollback

Quota enforcement can be disabled without code changes:

- Set `FILES_QUOTA_POLICY_DRY_RUN=true` to keep policy reporting while disabling upload blocking.
- Set `FILES_QUOTA_POLICY_ENABLED=false` to disable quota policy evaluation.

Existing audit events remain immutable evidence and do not require migration during rollback.

## Safety Boundary

This evidence explicitly does not enable:

- content upload beyond normal existing upload authorization;
- provider calls or external services;
- cleanup execution, physical deletion, S3 deletion, or scheduler loops;
- pdf-mineru parsing, translation provider calls, or Word generation.
