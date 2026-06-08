# Phase 7 real S3 delete guarded execution

## Goal

Execute a real S3 exact-object delete only after destructive rollout planning is accepted and the user explicitly approves one target.

Current status: blocked.

## Requirements

- Require accepted `phase7-real-s3-delete-guarded-rollout-planning` with exact bucket/key/version/sentinel.
- Require signed deletion plan hash.
- Require explicit destructive approval for exactly one target.
- Use the guarded product delete path; do not run ad hoc provider delete commands.
- Do not execute batch, prefix-wide, delete-all, scheduler-driven, or LocalStack delete in this task.

## Acceptance Criteria

- [x] Execution task exists and is explicitly blocked.
- [x] Destructive preconditions are documented.
- [x] No real S3 delete or LocalStack delete was run.

## Notes

- Do not start execution until planning and destructive approval are accepted.
