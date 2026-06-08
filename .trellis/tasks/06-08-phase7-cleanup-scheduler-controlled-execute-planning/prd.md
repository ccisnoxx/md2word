# Phase 7 cleanup scheduler controlled execute planning

## Goal

Plan cleanup scheduler controlled execute only after real S3 delete guarded execution has accepted evidence.

Current status: blocked because real S3 delete acceptance does not exist.

## Requirements

- Scheduler execute must depend on accepted `phase7-real-s3-delete-guarded-execution`.
- Scheduler execute must call the same guarded delete path as manual execution.
- Scheduler execute must remain disabled by default.
- Dry-run/history must remain the default operator workflow.
- Planning must require per-file eligibility, signed plan, preview hash, cleanup lock, bounded batch size, retry limits, and failure history.
- Scheduler must not bypass exact-target or signed-plan gates.
- First rollout must start with no-op/dry-run schedule and explicit manual promotion.

## Acceptance Criteria

- [x] Scheduler planning task exists and is explicitly blocked.
- [x] Dependency on accepted real S3 delete is documented.
- [x] No scheduler execute was run.

## Notes

- Do not start scheduler planning as executable work until real S3 delete acceptance exists.
