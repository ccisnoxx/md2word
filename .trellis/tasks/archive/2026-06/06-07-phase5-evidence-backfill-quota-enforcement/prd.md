# Phase 5 evidence backfill quota enforcement

## Goal

Backfill Phase 5 archive evidence for current quota ready-state upload blocking and Admin override behavior, reconciling the earlier Phase 5 closeout statement that quota upload blocking was still deferred.

## Requirements

- Treat this as evidence backfill for existing behavior.
- Confirm dry-run mode remains read-only and does not block upload authorization.
- Confirm ready policy blocks `/api/v1/files/upload-url` when projected usage reaches the block threshold.
- Confirm blocking writes `file.quota_policy_block` audit details and does not create upload authorization metadata.
- Confirm Admin override requires explicit reason and exact confirmation phrase.
- Confirm override writes `file.quota_policy_override` audit details and then continues normal upload authorization.
- Confirm rollback path is configuration-only: set `FILES_QUOTA_POLICY_DRY_RUN=true` or `FILES_QUOTA_POLICY_ENABLED=false`.
- Do not add new quota behavior, external calls, cleanup, provider calls, deletion, scheduler loops, or conversion workflow execution.

## Acceptance Criteria

- [x] Quota dry-run reports `would_block` without side effects.
- [x] Dry-run policy does not block real upload authorization.
- [x] Ready policy blocks upload authorization and writes structured audit.
- [x] Admin override allows upload authorization and writes structured audit.
- [x] API docs describe ready enforcement and rollback configuration.
- [x] Targeted backend tests pass.
- [x] Frontend build passes.
- [x] Trellis validate passes.
- [x] `git diff --check` passes.

## Notes

- This backfill resolves the Phase 6 gap-audit item for quota enforcement behavior drift.
- Phase 6 quota hardening should focus on operations UI, rollback/runbook, and audit replay rather than first implementation of blocking.
