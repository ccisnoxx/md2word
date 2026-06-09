# Phase 8 post-rollout architecture/status backfill design

## Scope

This task updates documentation and status records only. It does not change application code, runtime configuration, deployment state, secrets, external integrations, or data.

## Source Facts

- Phase 6 completed real-integration readiness foundations and moved real Slack/webhook, real S3 delete, cleanup scheduler execute, and real provider cancellation out of Phase 6 execution scope.
- Phase 7 implemented and validated the Slack webhook delivery pilot in no-live mode, prepared live-smoke gating, then deferred the live send by operator decision.
- Hostdzire deployment was updated and API/worker rebuilt/restarted during Phase 7, but `OPS_SLACK_WEBHOOK_URL` was not injected into active runtime env and no live send occurred.
- Provider cancellation remains blocked because provider evidence still does not support a real adapter.
- Real S3 delete remains a separate destructive controlled rollout and has not been executed.
- Cleanup scheduler controlled execute depends on accepted real S3 delete evidence and remains blocked.

## Documentation Targets

- `.codestable/architecture/backend-fastapi-service.md`
  - Primary architecture backfill target.
  - Add current `/ops` route, integration control plane, real alert delivery contract, S3 delete contract, cleanup history/lock/signed plan, quota enforcement, and blocked/deferred status.
- `.codestable/architecture/ARCHITECTURE.md`
  - Index-only update for external route list, core terms, current data/state, and known boundaries.
- `.codestable/roadmap/real-integration-readiness/real-integration-readiness-roadmap.md`
  - Preserve Phase 6/7 historical decisions and append Phase 8 status backfill facts.
- `.codestable/roadmap/real-integration-readiness/real-integration-readiness-items.yaml`
  - Make machine-readable status match the roadmap: Phase 7 is deferred/blocked and Phase 8 is documentation backfill only.

## Constraints

- Architecture docs must describe current implementation and operational status, not future plans.
- All secret references must remain names only; no secret value is read or written.
- No live send, provider cancellation, S3/LocalStack delete, scheduler execute, conversion workflow, SSH/deploy, stage, commit, or push is part of this task.

## Verification

- Trellis task validation.
- YAML parse for `real-integration-readiness-items.yaml`.
- `git diff --check`.
- Manual diff review for absence of live/external/destructive command changes.
