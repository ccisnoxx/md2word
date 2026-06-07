# Phase 6 Real Production Integration Readiness Roadmap Gap Audit Implementation Plan

## Task Classification

Planning/design only. No product implementation is included in this task.

## Completed Planning Work

- [x] Read project instructions and Trellis workflow.
- [x] Read Phase 5 production ops acceptance closeout.
- [x] Read Phase 5 release readiness and commit prep.
- [x] Inventory archived Phase 5 tasks under `.trellis/tasks/archive/2026-06/`.
- [x] Inspect current git status and diff summary without staging or modifying existing product files.
- [x] Inspect current backend/frontend/API/config/models/persistence/tests enough to classify Phase 6 gaps.
- [x] Read untracked CodeStable quota and real-integration planning artifacts.
- [x] Create this Trellis Phase 6 planning task.
- [x] Document Phase 5 review-separately classification.
- [x] Document Phase 6 roadmap, gap audit, safety plan, slice plan, and first recommended order.

## Implementation Guardrails For Future Tasks

- Do not start real integration implementation before the newly backfilled Phase 5 evidence is reviewed or explicitly waived.
- Do not run the pdf-mineru parsing, translation, or Word generation main workflow as part of Phase 6 planning.
- Do not call real Slack/email/webhook services without an explicit future task and user-approved test destination.
- Do not call real provider cancellation without provider semantics verification and explicit user approval.
- Do not perform real S3 deletion before LocalStack/fake parity, exact-target contract, signed plan, audit, idempotency, and rollback gates are accepted.
- Do not add autonomous destructive cleanup scheduling until delete safety and scheduler policy are accepted.
- Do not stage, commit, push, revert, or clean dirty worktree changes unless explicitly requested.

## Recommended First Batch

1. `phase5-evidence-backfill-audit-details-ui` - completed in `.trellis/tasks/archive/2026-06/06-07-phase5-evidence-backfill-audit-details-ui/`
   - Purpose: archive existing `frontend/src/pages/AuditLogPage.vue` behavior as Phase 5 evidence.
   - Verification target: focused frontend build/UI evidence and backend audit details/export tests already relevant to this surface.

2. `phase5-evidence-backfill-provider-cancellation-hardening` - completed in `.trellis/tasks/archive/2026-06/06-07-phase5-evidence-backfill-provider-cancellation-hardening/`
   - Purpose: archive existing `app/domains/ops/provider_cancellation.py` fake adapter hardening.
   - Verification target: provider cancellation fake preview/fake-cancel/dedupe/eligibility tests, with proof that no provider call or local job mutation occurs.

3. `phase5-evidence-backfill-quota-enforcement` - completed in `.trellis/tasks/archive/2026-06/06-07-phase5-evidence-backfill-quota-enforcement/`
   - Purpose: reconcile Phase 5 closeout drift by accepting current ready upload blocking and Admin override behavior.
   - Verification target: quota upload blocking, override, dry-run non-enforcement, API docs/OpenAPI consistency, and UI wording audit.

4. `integration-control-plane` - completed in `.trellis/tasks/archive/2026-06/06-07-phase6-integration-control-plane/`
   - Purpose: create shared disabled-by-default readiness/kill-switch control for all real integrations.
   - Verification target: all capabilities blocked by default; no provider/delete/scheduler side effect reachable.

5. `quota-enforcement-ops-hardening` - completed in `.trellis/tasks/archive/2026-06/06-07-phase6-quota-enforcement-ops-hardening/`
   - Purpose: make existing quota enforcement production-operable before introducing new real integrations.
   - Verification target: Admin-visible state, rollback path, audit replay, read-only safety flags, and no change to existing upload authorization behavior except documented config states.

6. `real-alert-delivery-adapter-contract` - completed in `.trellis/tasks/archive/2026-06/06-07-phase6-real-alert-delivery-adapter-contract/`
   - Purpose: define real alert provider adapter contract without calling live external services.
   - Verification target: fake/local parity, timeout/error/idempotency/dedupe/audit details tests, with real delivery still blocked.

7. `provider-cancellation-semantics-verification` - completed in `.trellis/tasks/archive/2026-06/06-07-phase6-provider-cancellation-semantics-verification/`
   - Purpose: verify whether current public MinerU docs support provider-side cancellation.
   - Verification target: Admin-visible read-only decision, source evidence, control-plane blocked status, and no provider calls or local mutation.

8. `s3-delete-localstack-contract` - completed in `.trellis/tasks/archive/2026-06/06-07-phase6-s3-delete-localstack-contract/`
   - Purpose: define S3 delete adapter contract and LocalStack/fake parity before any real delete work.
   - Verification target: Admin-only read-only Ops contract, linked file-retention fake contract version, control-plane blocked status, frontend visibility, OpenAPI/docs, and proof that no S3/LocalStack delete, cleanup execute, scheduler execute, metadata mutation, provider call, or audit write occurs.

## Verification For This Planning Task

- Run Trellis validation for this task after documents are written.
- Do not run unit tests, frontend build, API export, provider calls, S3 calls, scheduler loops, or conversion workflows for this planning-only task.

## Residual Risks

- The dirty worktree includes Phase 5 product changes that this task did not modify. Future implementation tasks must isolate their diffs carefully.
- Quota upload blocking is already present in current code. Until Phase 5 evidence is backfilled, release documentation and current behavior remain partially inconsistent.
- Provider cancellation real feasibility is currently blocked: public MinerU docs checked in `provider-cancellation-semantics-verification` do not expose a real cancellation contract.
- Real S3 deletion and scheduler execute carry destructive risk and must stay behind future explicit approval gates.
