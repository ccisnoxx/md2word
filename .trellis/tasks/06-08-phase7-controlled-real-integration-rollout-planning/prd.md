# Phase 7 controlled real integration rollout planning

## Goal

Plan Phase 7 controlled rollout for real integration capabilities after Phase 6 readiness foundations, without executing any real external, destructive, scheduler, provider-cancellation, conversion, staging, commit, or push action.

Phase 7 theme: Controlled rollout planning for selected real integrations.

## Requirements

- Keep this task in Trellis `planning` status. Do not run `task.py start` until the user reviews the planning artifacts and explicitly approves execution.
- Treat the Phase 6 closeout decision as binding:
  - Phase 6 is accepted only as `real integration readiness foundations completed`.
  - Real destructive or external execution remains gated or deferred.
- Decide whether Phase 7 should use `slack-webhook-delivery-pilot` as the lowest-risk minimum closed loop.
- Decide whether `real-s3-delete-guarded-execution` must be planned separately as a destructive controlled rollout.
- State that `cleanup-scheduler-controlled-execute` depends on acceptance of guarded real S3 deletion and must not become the first real destructive execution path.
- Keep `real-provider-cancellation-adapter` blocked unless primary provider evidence changes or a private provider contract is approved.
- Define rollout lanes, dependencies, approval gates, rollback expectations, and future Trellis task boundaries.
- Preserve capability independence: alert delivery, S3 deletion, cleanup scheduler execute, and provider cancellation must not share a single real-integration enablement switch.
- Do not create, execute, or test real Slack/webhook delivery, real provider cancellation, real S3 delete, LocalStack delete, scheduler execute, conversion main flow, or other external/destructive workflows in this planning task.
- Do not stage, commit, push, branch-switch, revert, or destructively clean files in this planning task.

## Inputs Reviewed

- `AGENTS.md`
- `.trellis/workflow.md`
- `.codestable/attention.md`
- `.trellis/tasks/archive/2026-06/06-08-phase6-closeout-acceptance/acceptance.md`
- `.codestable/roadmap/real-integration-readiness/real-integration-readiness-roadmap.md`
- `.codestable/roadmap/real-integration-readiness/real-integration-readiness-items.yaml`

## Non-Goals

- No production code changes.
- No live Slack, email, webhook, provider, S3, scheduler, LocalStack, or conversion workflow execution.
- No metadata mutation for delete or cleanup outcomes.
- No migration of provider cancellation from blocked to runnable state.
- No release-gate implementation beyond planning the future gate shape.

## Acceptance Criteria

- [x] A Trellis planning task exists with slug `phase7-controlled-real-integration-rollout-planning`.
- [x] The task stays in `planning` status.
- [x] `prd.md`, `design.md`, and `implement.md` document Phase 7 controlled rollout planning.
- [x] `slack-webhook-delivery-pilot` is classified as the recommended lowest-risk minimum closed loop for Phase 7, subject to future explicit live-send approval.
- [x] `real-s3-delete-guarded-execution` is classified as a separate destructive controlled rollout, not bundled into the Slack/webhook pilot.
- [x] `cleanup-scheduler-controlled-execute` is explicitly dependent on accepted guarded real S3 deletion.
- [x] `real-provider-cancellation-adapter` remains blocked unless provider evidence or a private provider contract changes.
- [x] Future task boundaries and approval gates are documented.
- [x] This planning task performs no real external/destructive/scheduler/conversion execution and no git staging/commit/push.

## Notes

- This task intentionally produces planning/design only. Future implementation tasks must be created and approved separately.
- The recommended Phase 7 first pilot is real alert delivery to one approved Slack/webhook destination because it has no intended product-state mutation and can be constrained to a single destination, single alert code set, explicit confirmation phrase, allowlist, rate limit, idempotency, audit, and kill-switch rollback.
