# Phase 6 quota enforcement ops hardening

## Goal

Close the operational gap around the already implemented quota enforcement path by giving Admin users a read-only control-plane view for:

- current quota enforcement readiness and kill-switch state
- concrete rollback switches
- replayable recent `file.quota_policy_block` and `file.quota_policy_override` audit evidence

## Requirements

- Add an Admin-only read endpoint for quota enforcement ops summary.
- The endpoint must be read-only and must not create upload authorizations, mutate `document_files`, write audit events, call providers, delete files, run cleanup, or start conversion work.
- The endpoint must summarize whether true upload blocking can currently execute.
- The endpoint must expose rollback options as explicit config switch recommendations, not execute rollback.
- The endpoint must replay recent quota enforcement audit events with safe structured details.
- File Retention UI must surface the ops summary near the quota dry-run area.
- API docs and OpenAPI snapshot must be kept current.

## Acceptance Criteria

- [ ] Admin can read quota enforcement ops summary.
- [ ] Operator is rejected from the ops summary endpoint.
- [ ] Summary includes enforcement readiness, rollback options, read-only safety flags, and recent quota block/override replay.
- [ ] Replay output preserves useful details such as outcome, trace id, projected usage, quota bytes, and override-applied flag.
- [ ] Reading the summary does not change file metadata or append audit events.
- [ ] File Retention page displays the summary, rollback options, safety flags, and replay rows.
- [ ] Targeted backend tests, OpenAPI export check, and frontend build pass.

## Notes

- This task hardens operations for an existing blocking capability; it must not enable any real external integration.
