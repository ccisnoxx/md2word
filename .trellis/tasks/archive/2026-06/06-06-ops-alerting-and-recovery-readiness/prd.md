# Ops alerting and recovery readiness

## Goal

Implement a read-only Admin operations alert readiness contract so Ops Dashboard alerts are produced by a stable backend API instead of only frontend-derived heuristics.

## Requirements

- Add an Admin-only backend endpoint for operations alert readiness.
- Endpoint must aggregate existing health readiness, stage spool observations, and document job status counters.
- Endpoint must return a stable summary, alert list, and safety metadata.
- Alerts must include severity, source, code, count, description, suggested route, and suggested action text.
- Endpoint must not execute retry, cancel, archive, recovery, cleanup, physical deletion, scheduler, provider calls, or notification delivery.
- Endpoint must not write audit events by default; it is a read-only status query.
- Frontend Ops Dashboard must call the new endpoint and render backend-provided alerts while keeping existing read-only health/job sample panels.
- Existing health `/ready` and `/metrics` behavior must remain compatible.
- OpenAPI and TypeScript contracts must be updated.

## Acceptance Criteria

- [x] Task exists.
- [x] `prd.md`, `design.md`, and `implement.md` define the read-only alert readiness boundary.
- [x] `task.py validate` passes before start.
- [x] `task.py start` is run.
- [x] Backend Admin-only `health/ops-alerts` endpoint is implemented.
- [x] Operator access is rejected.
- [x] Alert response covers readiness blockers/warnings, failed stage messages, stale running messages, replayable messages, failed jobs, and running jobs.
- [x] Response includes explicit safety metadata showing no recovery/write actions executed.
- [x] Frontend Ops Dashboard consumes backend alert readiness.
- [x] OpenAPI snapshot is regenerated and OpenAPI tests pass.
- [x] Frontend build passes.
- [x] `task.py validate` passes after implementation.
- [x] `git diff --check` passes.

## Notes

- This is not alert delivery. No email, Slack, webhook, cron, daemon, or external notification is added.
- This is not recovery execution. It only provides suggested next steps and routes.
- Do not run pdf-mineru parsing, real translation providers, Word generation, physical deletion, S3 deletion, quota enforcement, scheduler loops, or provider cancellation flows.
