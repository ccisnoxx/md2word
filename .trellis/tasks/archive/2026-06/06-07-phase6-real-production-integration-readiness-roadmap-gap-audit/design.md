# Phase 6 Real Production Integration Readiness Roadmap Gap Audit Design

## Decision

Proceed with Phase 6 as a planning roadmap, not as implementation. The first Phase 6 implementation work should not enable any real external side effect. The previously unarchived Phase 5 behaviors already present in the dirty worktree now have backfilled evidence:

- Audit Log structured details UI: `.trellis/tasks/archive/2026-06/06-07-phase5-evidence-backfill-audit-details-ui/`.
- Provider cancellation fake adapter hardening: `.trellis/tasks/archive/2026-06/06-07-phase5-evidence-backfill-provider-cancellation-hardening/`.
- Quota ready-state upload blocking and Admin override: `.trellis/tasks/archive/2026-06/06-07-phase5-evidence-backfill-quota-enforcement/`.

The Phase 6 technical direction is to add a real-integration control plane first, then bring each real production integration online behind independent readiness gates, disabled-by-default flags, dry-run or preview flows, explicit confirmation, idempotency, structured audit details, and rollback/runbook evidence.

## Phase 5 Release-Readiness Review-Separately Inventory

| Item | Current Evidence | Classification | Required Next Action |
| --- | --- | --- | --- |
| `.codex/config.toml` | Untracked local/private Codex config. Not referenced by product code or Phase 5 acceptance evidence. | Keep out of product release scope. | Do not commit unless the user explicitly asks and private values are reviewed. |
| `frontend/src/pages/AuditLogPage.vue` | Current UI renders structured audit details with drawer/search/export behavior. | Resolved Phase 5 evidence gap. | Evidence backfilled in `.trellis/tasks/archive/2026-06/06-07-phase5-evidence-backfill-audit-details-ui/`; Phase 6 can use it as audit replay foundation. |
| `app/domains/ops/provider_cancellation.py` | Current fake adapter includes structured adapter result, idempotency key, dedupe from audit details, timeout fields, and eligibility gates. | Resolved Phase 5 evidence gap. | Evidence backfilled in `.trellis/tasks/archive/2026-06/06-07-phase5-evidence-backfill-provider-cancellation-hardening/`; Phase 6 should start provider work with semantics verification instead of real cancellation. |
| `.codestable/features/2026-06-07-quota-enforcement-design/` | CodeStable note says ready quota policy now blocks `/files/upload-url` and Admin override can allow upload. Tests and docs also reflect this. Phase 5 closeout still listed upload blocking as deferred. | Resolved Phase 5 behavior drift and evidence gap. | Evidence backfilled in `.trellis/tasks/archive/2026-06/06-07-phase5-evidence-backfill-quota-enforcement/`; Phase 6 scope becomes ops hardening, UI consistency, readiness, rollback, and audit replay, not the initial blocker implementation. |
| `.codestable/roadmap/real-integration-readiness/` | CodeStable roadmap already sketches Phase 6 capabilities and dependency items. | Valid Phase 6 planning input, not release evidence by itself. | Mirror the useful content into this Trellis task and use Trellis as the reviewable planning artifact. |

## Current State and Gap Audit

### Real Integration Control Plane

Current state:

- Settings include dry-run and enablement flags for quota and staged destination config.
- Ops and files APIs enforce Admin role on high-risk endpoints.
- Existing safety is implemented per module, not as a shared capability gate.

Gaps:

- No shared capability model for `alert_delivery`, `provider_cancellation`, `s3_delete`, `cleanup_scheduler_execute`, and `quota_enforcement`.
- No centralized readiness status, kill switch, release gate, or secret-reference status per real integration.
- Current frontend cannot show one consolidated real-integration readiness surface.

Phase 6 outcome:

- Add a disabled-by-default control plane that resolves per-capability readiness, dry-run-only state, kill switch state, blocking reasons, and safe config summaries.

### Slack/Email/Webhook Delivery Readiness

Current state:

- Alert destination config supports Slack/email/webhook dry-run validation with secret refs.
- Alert delivery supports preview and fake-send to local outbox only.
- Fake delivery writes structured audit details and dedupes.

Gaps:

- No real delivery provider adapter.
- No secret resolver boundary for real send.
- No delivery history beyond audit events.
- No timeout/error/idempotency contract for provider responses.
- No real delivery release gate or rollback runbook.

Phase 6 outcome:

- First define provider protocol and fake/local parity tests.
- Then pilot one exact Slack or webhook destination behind explicit enablement and confirmation.

### Provider Cancellation Readiness

Current state:

- Fake provider cancellation is exact-target, audited, deduped, and non-mutating.
- Eligibility requires queued/running target state and provider operation identifiers.
- Current implementation does not call a real provider.

Gaps:

- MinerU/provider cancellation semantics are not verified from primary provider docs or a safe non-mutating contract.
- No real cancellation adapter, endpoint, or release gate.
- No guarantee that provider cancellation is idempotent, supported, or distinguishable from local job cancellation.

Phase 6 outcome:

- First produce provider cancellation semantics verification.
- Only if supported, implement a real adapter that never auto-mutates local job state and remains exact-target/audited/idempotent.

### S3 Deletion Readiness

Current state:

- Local file and local object deletion can execute under retention safety checks.
- S3 deletion is intentionally fake-only and returns an exact-target fake contract.
- Cleanup run preview hash and signed plan foundations exist.

Gaps:

- No LocalStack or equivalent contract test for a real S3 delete adapter.
- No real S3 delete provider result contract with version/etag/idempotency.
- No safe metadata mutation rule for real S3 delete success.

Phase 6 outcome:

- First add LocalStack/fake-provider parity for exact S3 deletion.
- Only later enable real S3 deletion behind exact bucket/key/version, signed plan, release gate, and rollback/runbook.

### Quota Enforcement Operations

Current state:

- Current backend blocks `/files/upload-url` when quota policy is enabled, not dry-run, status is ready, and projected usage crosses the block threshold.
- Admin override is supported with reason and confirmation.
- Tests cover block, override, and dry-run non-enforcement.
- Phase 5 evidence is backfilled in `.trellis/tasks/archive/2026-06/06-07-phase5-evidence-backfill-quota-enforcement/`.

Gaps:

- File Retention UI text still emphasizes dry-run and may not clearly expose real upload blocking readiness/rollback.
- Need config readiness, audit details replay, and runbook for enabling/disabling quota enforcement in production.

Phase 6 outcome:

- Treat core blocking as already implemented and archived via the Phase 5 evidence backfill.
- Harden UI, readiness, rollback, audit replay, and release checks after the Phase 5 evidence gap is closed.

### Cleanup Scheduler Safety

Current state:

- Manual scheduler dry-run exists and records history under a lock.
- Cleanup run preview/execute supports history and signed plan for manual execution.
- No autonomous cleanup execution loop exists.

Gaps:

- No disabled-by-default scheduler execute loop.
- No scheduler policy for max files, lock ttl, signed plan lifecycle, retry, failure recording, and S3 gate dependency.
- Scheduler execute cannot be safe before real S3 deletion has a guarded contract.

Phase 6 outcome:

- Keep scheduler dry-run as the default.
- Defer controlled execute until real S3 deletion safety is proven.
- Any future scheduler execute must use lock, preview hash, signed plan, exact delete eligibility, bounded batch size, and failure audit/history.

### Audit Details, Replay, and Release Evidence

Current state:

- Audit events support structured details.
- Backend list/export includes details search and `details_json`.
- Frontend Audit Log details UI evidence is backfilled in `.trellis/tasks/archive/2026-06/06-07-phase5-evidence-backfill-audit-details-ui/`.

Gaps:

- No unified real-integration audit schema across delivery/cancel/delete/scheduler/quota.
- No compliance replay or release-gate script that verifies real integration safety fields.
- The current UI evidence is accepted as a Phase 6 foundation.

Phase 6 outcome:

- Standardize integration audit details and replay queries.
- Include safe export/redaction expectations and release checks.

## Phase 6 Safety Plan

All Phase 6 real-side-effect features must satisfy this contract before real execution is allowed:

- Capability-specific flag defaults to disabled.
- Dry-run-only mode defaults to true when available.
- Capability-specific kill switch can block execution even if enabled.
- Endpoint requires Admin or explicitly approved operator role.
- Request selects exact targets; no bulk implicit target selection.
- Request requires reason and confirmation phrase for real side effects.
- Preview/dry-run response exists and is safe to run repeatedly.
- Idempotency key is stable for the exact action and target.
- Dedupe prevents duplicate provider calls inside a configured window.
- Timeout and retry behavior are bounded and audited.
- Provider response body, secret values, webhook URLs, authorization headers, file bytes, prompts, and local filesystem paths are never written to API responses, audit events, history, logs, or frontend state.
- Audit details include gate snapshot, contract version, adapter mode, idempotency key, timeout, outcome, non-sensitive external request id, provider-call/delete-executed booleans, and safety booleans.
- History records can prove whether the action was previewed, executed, skipped, failed, deduped, timed out, or blocked.
- Rollback/runbook explains how to disable the capability, activate the kill switch, inspect audit/history, and handle partial failures.
- Verification must include fake/local parity before any real provider execution.

Additional per-capability constraints:

- Real alert delivery must not send before destination allowlist, secret ref, dedupe, rate limit, and provider timeout contracts are verified.
- Real provider cancellation must not be implemented until provider semantics are verified. It must not automatically cancel or mutate local jobs.
- Real S3 deletion must require exact bucket/key and optional version/etag, and metadata may be marked deleted only after provider delete success or a proven already-missing idempotent result.
- Scheduler execute must remain disabled until real deletion contracts and signed plan safety are proven. It must never bypass per-file eligibility.
- Quota enforcement must have a documented rollback path to dry-run or disabled mode and an Admin override audit trail.

## Phase 6 Slice Plan

| Slice | Risk | Depends On | Scope | Exit Criteria |
| --- | --- | --- | --- | --- |
| phase5-evidence-backfill-audit-details-ui | Low | Current dirty worktree | Backfilled Trellis evidence for existing Audit Log details UI. | Completed: `.trellis/tasks/archive/2026-06/06-07-phase5-evidence-backfill-audit-details-ui/`. |
| phase5-evidence-backfill-provider-cancellation-hardening | Low | Current dirty worktree | Backfilled Trellis evidence for existing fake adapter hardening. | Completed: `.trellis/tasks/archive/2026-06/06-07-phase5-evidence-backfill-provider-cancellation-hardening/`. |
| phase5-evidence-backfill-quota-enforcement | Medium | Current dirty worktree | Backfilled Trellis evidence for quota ready upload blocking and Admin override. | Completed: `.trellis/tasks/archive/2026-06/06-07-phase5-evidence-backfill-quota-enforcement/`. |
| integration-control-plane | Low | Phase 5 evidence backfilled | Implemented shared capability flags, kill switches, readiness summaries, and safe status exposure. | Completed: `.trellis/tasks/archive/2026-06/06-07-phase6-integration-control-plane/`; all real external/destructive capabilities report disabled or blocked by default and no provider calls are possible. |
| quota-enforcement-ops-hardening | Medium | Phase 5 quota evidence, integration-control-plane | UI consistency, readiness display, rollback/runbook, audit replay for quota block/override. | Completed: `.trellis/tasks/archive/2026-06/06-07-phase6-quota-enforcement-ops-hardening/`; Admin can see quota enforcement state, rollback switches, read-only safety flags, and block/override audit replay without changing upload behavior. |
| real-alert-delivery-adapter-contract | Medium | integration-control-plane | Provider protocol, fake-provider parity, history/audit schema, timeout/error/idempotency contract. | Completed: `.trellis/tasks/archive/2026-06/06-07-phase6-real-alert-delivery-adapter-contract/`; tests prove adapter contract and fake parity without live Slack/email/webhook calls. |
| slack-webhook-delivery-pilot | Medium-High | real-alert-delivery-adapter-contract | One exact Slack or webhook destination, disabled by default, explicit confirmation. | Real send only possible with explicit enablement and user-approved external service setup. |
| provider-cancellation-semantics-verification | Medium | integration-control-plane | Read primary provider docs/API semantics and decide whether real cancel is supported. | Completed: `.trellis/tasks/archive/2026-06/06-07-phase6-provider-cancellation-semantics-verification/`; written decision is `unsupported_by_public_docs`, no real cancellation occurs. |
| real-provider-cancellation-adapter | High | provider-cancellation-semantics-verification | Real adapter and UI/API gate if provider supports cancellation. | Exact target cancellation is audited/idempotent and never auto-mutates local jobs. |
| s3-delete-localstack-contract | Medium | integration-control-plane | LocalStack or equivalent fake-provider contract for exact S3 delete. | Completed: `.trellis/tasks/archive/2026-06/06-07-phase6-s3-delete-localstack-contract/`; contract proves version/etag/idempotency/metadata rules without real S3 deletion, LocalStack execution, metadata mutation, cleanup execute, or scheduler execute. |
| real-s3-delete-guarded-execution | High | s3-delete-localstack-contract | Real S3 delete behind exact target, signed plan, audit/history, and kill switch. | Real delete only executes under explicit enablement and verified release gate. |
| cleanup-scheduler-controlled-execute | High | real-s3-delete-guarded-execution | Disabled-by-default scheduler execute loop using lock/history/signed plan. | Scheduler cannot execute unless all gates pass; dry-run remains default. |
| real-integration-audit-replay | Medium | Audit UI evidence, adapter contracts | Unified audit details schema, replay/export, UI review of real integration evidence. | Compliance evidence can be replayed without exposing secrets. |
| phase6-release-gate-runbook | Medium | All real integration pilots selected for release | Release checks, rollback instructions, kill-switch smoke, fake/local parity checks. | Phase 6 release can be accepted without relying on undocumented manual knowledge. |

## Recommended First Implementation Order

1. `quota-enforcement-ops-hardening` is completed; upload blocking now has Admin-visible readiness, rollback guidance, read-only safety flags, and audit replay.
2. `real-alert-delivery-adapter-contract` is completed; fake alert delivery now emits same-version adapter evidence and contract report while real sending remains blocked.
3. `provider-cancellation-semantics-verification` is completed; current public MinerU docs do not expose a provider-side cancellation contract, so real provider cancellation remains blocked.
4. `s3-delete-localstack-contract` is completed; Ops now exposes the S3 delete adapter contract, LocalStack profile, and file-retention fake parity while real S3 delete remains blocked.
5. Choose `slack-webhook-delivery-pilot` only after the user approves a test destination and secret-ref setup, or proceed to `real-s3-delete-guarded-execution` only after accepting the destructive-risk gates.
6. Defer `cleanup-scheduler-controlled-execute` until exact-target real S3 delete safety, signed plan behavior, and rollback are proven.
7. Build `real-integration-audit-replay` and `phase6-release-gate-runbook` once the first real integration contract is stable, then extend them per capability.

## Open Questions For Review

- Should Phase 6 minimum viable real integration be Slack/webhook delivery, because it has lower state mutation risk than provider cancellation or S3 deletion?
- Should quota enforcement UI text be corrected immediately in the Phase 5 evidence backfill or deferred to Phase 6 hardening?
- Which secret resolver pattern should be used for real integrations: environment-only refs, existing settings provider, or a dedicated secret lookup port?
- Is LocalStack acceptable for S3 delete contract verification, or should the project use an in-memory S3-compatible fake first?
