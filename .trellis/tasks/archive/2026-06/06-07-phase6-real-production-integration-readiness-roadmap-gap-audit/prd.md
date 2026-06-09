# Phase 6 real production integration readiness roadmap gap audit

## Goal

Plan Phase 6 real production integration readiness by auditing Phase 5 release-readiness gaps, safety contracts, dependencies, and implementation slices without enabling real external side effects.

Phase 6 theme: Real Production Integration Readiness.

## Requirements

- Inventory the Phase 5 release-readiness `review-separately` items and classify each item as one of:
  - Phase 6 scope input.
  - Phase 5 archive or acceptance evidence gap that must be resolved before Phase 6 implementation.
  - Local/private workspace item that should stay out of product release scope.
- Audit current backend, frontend, API docs, data models, config, persistence wiring, and tests against the Phase 5 acceptance closeout and release-readiness conclusions.
- Produce a Phase 6 roadmap that covers real Slack/email/webhook delivery readiness, real provider cancellation readiness, real S3 deletion readiness, quota enforcement operations, autonomous cleanup scheduler safety, structured audit details UI, provider cancellation adapter hardening, and CodeStable planning artifact alignment.
- Define safety contracts before any real external side effect, deletion, scheduler execution, or provider cancellation:
  - Disabled-by-default capability flags and kill switches.
  - Dry-run, preview, explicit confirmation, exact target selection, idempotency, dedupe, bounded timeout, structured audit, history, and rollback expectations.
  - Secret-reference boundaries that never expose secret values in settings JSON responses, audit events, history, exports, logs, or frontend state.
- Split Phase 6 into small, dependency-aware implementation slices with risk labels and a first recommended order.
- Keep this task in planning/design only. Do not implement code, run the pdf-mineru/translation/Word main workflow, call real external alert services, call real provider cancellation, perform real S3 deletion, add autonomous destructive scheduling, stage, commit, or push.

## Inputs Reviewed

- `AGENTS.md`
- `.trellis/workflow.md`
- Phase 5 production ops acceptance closeout: `prd.md`, `design.md`, `implement.md`, `acceptance.md`
- Phase 5 release readiness and commit prep: `prd.md`, `design.md`, `implement.md`, `acceptance.md`
- All archived Phase 5 tasks under `.trellis/tasks/archive/2026-06/`
- Current `git status --short`, `git diff --stat`, and tracked diff name summary
- Current backend code for config/runtime, ops alert delivery, alert destinations, provider cancellation, audit, file quota, file retention cleanup, cleanup history, cleanup lock, S3 deletion contract, scheduler dry-run, persistence adapters, and app wiring
- Current frontend pages and API wrappers for Ops Dashboard, File Retention, Audit Log, files APIs, ops APIs, and shared types
- Current API documentation and OpenAPI outputs under `docs/api/`
- Current tests covering ops fake alert delivery, alert destination dry-run, provider cancellation fake adapter, audit details/export, quota dry-run and ready upload blocking, S3 fake deletion contract, cleanup run history/signed plan, cleanup lock, and scheduler dry-run
- CodeStable planning artifacts:
  - `.codestable/features/2026-06-07-quota-enforcement-design/quota-enforcement-design-ff-note.md`
  - `.codestable/roadmap/real-integration-readiness/real-integration-readiness-roadmap.md`
  - `.codestable/roadmap/real-integration-readiness/real-integration-readiness-items.yaml`

## Non-Goals

- No production feature implementation in this planning task.
- No live Slack, email, webhook, provider, S3, scheduler, or conversion workflow execution.
- No mutation of existing Phase 5 dirty worktree content except Trellis planning documents for this task.
- No git staging, commit, push, branch switch, destructive cleanup, or revert.

## Acceptance Criteria

- [x] Phase 5 `review-separately` items are classified with a required next action.
- [x] Phase 6 roadmap and gap audit are documented in `design.md`.
- [x] Safety plan covers external delivery, provider cancellation, S3 deletion, scheduler execution, quota enforcement, audit, secret handling, idempotency, and rollback.
- [x] Phase 6 work is split into small tasks by dependency and risk.
- [x] First recommended implementation order is documented.
- [x] The task remains in Trellis `planning` status and no product code is implemented.

## Notes

- Current code already includes ready-state quota upload blocking and Admin override behavior, while Phase 5 closeout still listed quota upload blocking as deferred. This is now backfilled by `.trellis/tasks/archive/2026-06/06-07-phase5-evidence-backfill-quota-enforcement/`.
- Current code also includes Audit Log structured details UI and provider cancellation fake adapter hardening. These are now backfilled by `.trellis/tasks/archive/2026-06/06-07-phase5-evidence-backfill-audit-details-ui/` and `.trellis/tasks/archive/2026-06/06-07-phase5-evidence-backfill-provider-cancellation-hardening/`.
