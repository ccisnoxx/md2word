# Phase 5 production ops integration automation gap audit design

## Inputs Reviewed

- `AGENTS.md`
- `.trellis/workflow.md`
- `.trellis/tasks/archive/2026-06/06-03-product-roadmap/{prd.md,design.md,implement.md,acceptance.md}`
- `.trellis/tasks/archive/2026-06/06-07-phase4-operations-retention-closeout/{prd.md,design.md,implement.md}`
- Phase 4 archive tasks for alert delivery, provider cancellation, automated cleanup, file retention, audit export, and ops dashboard.
- Current backend Ops/File/Audit APIs and services:
  - `app/domains/ops/{router.py,schemas.py,recovery_actions.py,alert_delivery.py,provider_cancellation.py}`
  - `app/domains/files/{router.py,schemas.py,service.py,cleanup_execution.py,storage_usage.py,scheduled_cleanup.py}`
  - `app/domains/audit/{models.py,query.py,router.py,schemas.py}`
  - `app/core/{config.py,runtime.py}`
- Current frontend Admin surfaces:
  - `frontend/src/pages/{OpsDashboardPage.vue,FileRetentionPage.vue,AuditLogPage.vue,SystemStatusPage.vue,JobDetailPage.vue}`
  - `frontend/src/api/{health.ts,opsRecoveryActions.ts,files.ts,types.ts}`
- Current docs and tests:
  - `docs/api/{ops.md,files.md,openapi.json}`
  - `tests/test_fastapi_jobs_backend.py`
  - `frontend/package.json`

## Current Phase 4 State

| Area | Current implementation | Gap for Phase 5 |
| --- | --- | --- |
| Ops alerts | `GET /api/v1/health/ops-alerts` and Admin-only fake local outbox endpoints exist. Recovery registry marks `alert.delivery` available only for fake delivery. | Frontend has no alert delivery preview/fake-send controls. No real Slack/email/webhook destination config, provider adapter, retry, or secret boundary. |
| Provider cancellation | Admin-only metadata preview and fake-cancel endpoints exist for exact `document_job` / `legacy_job` MinerU targets. No local job mutation or provider call. | Frontend has no provider cancellation controls. MinerU client still has no real cancel adapter, fake-client matrix, timeout/error semantics, or provider response audit. |
| Cleanup execution | Admin-only manual cleanup-run preview/execute exists and reuses physical delete safety contract with `preview_hash`. S3 is skipped. | Frontend has no cleanup-run wrapper/types/buttons. No run history, signed cleanup plan, lock, or scheduler loop. |
| File retention / S3 | Local/local_object physical delete is guarded. S3 delete is explicitly skipped. Storage usage/quota is advisory-only. | No S3 delete safety adapter, no real cloud-delete contract, no quota policy enforcement or upload blocking. |
| Audit | Admin list/export exists. Execution contracts write compact audit events in `reason`. | No structured `details`, no per-file durable evidence, no execution result object suitable for compliance replay. |
| Frontend Ops | Ops dashboard is read-only and lists recovery action registry. File retention page supports retention plan, policy, file library, storage usage, mark-expired, and physical delete. | New Phase 4 fake/execution contracts are not exposed as safe operator workflows. |
| Config | Settings include S3 storage, MinerU, auth, worker, upload limits, retention days. | No alert destination config, no quota threshold config, no scheduler config, no provider-cancel feature flag or endpoint contract. |

## Candidate Decisions

| Candidate | Phase 5 decision | Reason |
| --- | --- | --- |
| 为 Phase 4 后端 fake/preview/execution contracts 补前端操作按钮 | Include first | Lowest external risk because backend contracts already enforce fake/preview/confirmation/audit. Start with alert fake delivery controls, then provider fake-cancel, then cleanup-run UI. |
| Structured audit details / per-file durable compliance evidence | Include early | This is the main prerequisite for deeper automation, S3 deletion, provider cancellation, and compliance replay. It should precede higher-risk execution expansion. |
| Real Slack/email/webhook alert delivery | Include as staged groundwork only | Phase 5 can add destination config schema, disabled-by-default adapter boundary, fake provider tests, allowlist and dry-run. Actual real send needs explicit approval and secrets; do not implement first. |
| Real provider cancellation integration | Include as staged groundwork only | Add provider adapter interface, fake MinerU cancellation client, idempotency/result contract, and provider-error tests before any real MinerU call. Actual real cancellation remains deferred until provider API semantics are verified. |
| Scheduler loop / autonomous cleanup executor / run history / distributed lock / signed cleanup plan | Partially include | Include run history and signed cleanup plan first. Distributed lock and disabled-by-default manual runner can follow. Autonomous destructive scheduler remains deferred. |
| Real S3 deletion safety contract | Include design/fake adapter later; defer real delete | Need provider-specific preview, version/bucket/key exactness, fake S3/localstack tests, and per-file audit details before real delete. Current Phase 5 should not execute real S3 delete. |
| Quota enforcement / upload blocking | Include as policy design and dry-run gate first | Current quota is advisory-only. Add quota policy/readiness config and an upload authorization dry-run block report first; actual blocking requires override/grace strategy and product approval. |

## Phase 5 Roadmap

### Slice Group A: Expose Existing Safe Contracts

Goal: Let Admin use already-reviewed fake/preview contracts from the UI without expanding backend side effects.

- `phase5-alert-delivery-frontend-controls`
  - Add frontend types/API wrapper for alert delivery preview/fake-send.
  - Add controls to `OpsDashboardPage.vue` for currently active backend alerts.
  - Execution remains fake local outbox only.
- `phase5-provider-cancellation-frontend-controls`
  - Add frontend types/API wrapper for provider cancellation preview/fake-cancel.
  - Add exact target workflow from job detail or Ops dashboard.
  - Execution remains fake cancellation only.
- `phase5-cleanup-run-frontend-controls`
  - Add cleanup-run TS types/API wrapper.
  - Add `preview_hash`-gated cleanup-run UI to `FileRetentionPage.vue`.
  - Must clearly distinguish physical delete and cleanup-run execution.

### Slice Group B: Durable Evidence Foundation

Goal: Replace compact audit `reason` as the only machine-readable evidence for high-risk Ops actions.

- Add structured audit detail model behind existing audit event contract.
- Preserve existing `reason` for compatibility and CSV export.
- Add per-file evidence for physical delete and cleanup-run execution.
- Add query/export support for structured details without exposing secrets, local paths, object bodies, prompt text, credentials, or provider payloads.

### Slice Group C: Integration Readiness Without Real External Calls

Goal: Introduce provider/destination abstractions in fake mode before real integration.

- Alert destination config and dry-run adapter:
  - destination identity, channel type, enabled flag, secret reference only, allowlist, rate-limit, dedupe.
  - fake send through adapter tests; no Slack/email/webhook call.
- Provider cancellation adapter:
  - provider capability interface, fake MinerU cancel client, timeout/error/idempotent result contract.
  - no real MinerU call.
- S3 deletion adapter safety contract:
  - exact bucket/key/version preview and fake S3 delete result tests.
  - no real S3 delete.

### Slice Group D: Automation Readiness

Goal: Make automation auditable before any autonomous execution.

- Cleanup run history with stable run ID and state transitions.
- Signed cleanup plan generated from preview hash and exact file IDs.
- Distributed lock design and disabled-by-default manual runner.
- Scheduler dry-run mode that writes run history but does not delete.
- Autonomous destructive scheduler remains outside Phase 5 until explicit approval.

### Slice Group E: Quota Policy Readiness

Goal: Move from advisory quota to enforceable policy safely.

- Add quota policy config and UI preview.
- Add upload authorization dry-run gate response that reports would-block/would-warn.
- Only after product approval, add actual upload blocking with admin override and audit.

## Safety Plan

All Phase 5 slices must keep these invariants:

- Admin-only for Ops execution controls.
- Exact target only:
  - exact `alert_codes`, no implicit all-alert delivery.
  - exact `target_type` + `target_id`, no bulk provider cancellation.
  - exact `file_ids`, no delete-all cleanup.
- Preview/dry-run first for every external, destructive, or automated action.
- Mutating execution requires non-empty reason.
- Irreversible or provider-side actions require exact confirmation phrase.
- Responses must include safety metadata proving which side effects did and did not happen.
- Audit must be compact for humans and structured for machines once details support lands.
- Idempotency must be explicit:
  - alert delivery dedupe by alert/window/channel.
  - provider cancellation by provider/target/operation ID.
  - cleanup by preview hash and physical-delete idempotent outcomes.
- External integrations must be disabled by default and testable with fake clients before real calls.
- Secrets must be referenced, not returned or written into audit/details.
- No Phase 5 task may run pdf-mineru parsing, real translation provider calls, Word generation, real alert delivery, real provider cancellation, real S3 deletion, MinerU recovery query/download, or an autonomous destructive scheduler unless a later task explicitly changes the safety plan with approval.

## First Batch Recommended Order

1. `phase5-alert-delivery-frontend-controls`
   - Lowest risk and highest UX clarity. Uses current active alerts and fake local outbox only.
2. `phase5-provider-cancellation-frontend-controls`
   - Similar fake-only backend contract, but higher product-semantics risk because users may confuse fake with real cancellation.
3. `phase5-structured-audit-details-foundation`
   - Unlocks durable compliance evidence before more destructive UI or integration work.
4. `phase5-cleanup-run-frontend-controls`
   - Destructive local deletion path exists; UI should land after audit/details plan is firm or with clear current compact-audit caveat.
5. `phase5-alert-destination-config-dry-run`
   - Starts real alert integration groundwork without sending anything.
6. `phase5-quota-policy-dry-run`
   - Adds enforcement design and dry-run upload gate before actual blocking.

Deferred from first batch:

- Real Slack/email/webhook send.
- Real MinerU/provider cancellation call.
- Real S3 delete.
- Autonomous cleanup scheduler.
- Distributed lock if no run history/signed plan exists yet.
