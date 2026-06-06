# Ops recovery action governance gap audit design

## Scope

This task is planning-only. It does not change backend code, frontend code, API contracts, persistence schemas, runtime settings, tests, scheduler behavior, provider integrations, notification delivery, or cleanup execution.

The output is a reviewable decision document for the next Phase 4 implementation slice after read-only ops alert readiness.

## Inputs Reviewed

| Input | Relevant conclusion |
| --- | --- |
| Product roadmap Phase 4 | Remaining scope includes worker/queue monitoring, alerting, recovery/cancel improvements, and data lifecycle automation. |
| `ops-alerting-and-recovery-readiness` | Adds Admin-only `GET /api/v1/health/ops-alerts`; explicitly read-only, no recovery/provider/notification action. |
| `file-retention-scheduled-cleanup-readonly-plan` | Adds read-only cleanup runner; report is advisory and does not mutate metadata or delete objects. |
| `file-retention-physical-delete-safety-contract` | Manual selected-file physical deletion exists with preview, confirmation, reason, Admin-only, audit, and per-file outcomes. |
| `audit-log-export-governance` | Backend audit export exists and records an audit event; no server-side export files or delivery. |
| `app/domains/document_jobs/service.py` | `retry_job`, `cancel_job`, and `archive_job` mutate document job metadata and events. Cancel is local state only and does not guarantee external provider interruption. |
| `app/domains/document_jobs/router.py` | Single and bulk retry/archive/cancel endpoints exist for authenticated users; resource rebinding is restricted where needed. |
| `app/domains/jobs/ops_router.py` | Legacy job ops include retry, cancel, recover MinerU result, and cleanup-local-files. `recover-mineru-result` actively queries provider and enqueues background processing. |
| `app/domains/jobs/lifecycle.py` | Legacy retry/cancel/cleanup write job state, stage messages, events, and audit. Cleanup deletes local work directories while preserving registered artifacts. |
| `app/domains/jobs/stage.py` | Stage replay and MinerU recovery can call provider query/download and conversion pipeline through background dispatch. |
| `app/clients/mineru_client.py` | Local client supports submit, query result, and download. No local provider cancellation method is implemented. |

## Current Capability Matrix

| Area | Current capability | Gap |
| --- | --- | --- |
| Read-only ops alerts | Backend and frontend show readiness, queue, and job risk signals. | Alerts only suggest routes/actions; no action safety registry or execution preview. |
| Document job retry | Existing `document_jobs` retry resets failed jobs, records event/audit, and may enqueue worker. | No central Ops action model that states required gates, blast radius, provider calls, or dry-run semantics. |
| Document job cancel | Existing cancel marks pending/queued/running jobs canceled and records event/audit. | Does not cancel provider-side work; UI copy says this honestly. No provider cancellation policy. |
| Document job archive | Existing archive hides terminal jobs and preserves records. | Not a recovery action, but should still be modeled as a low-risk metadata action in an action registry if exposed from Ops. |
| Legacy job retry/cancel | Existing legacy operations mutate status/stage messages and audit. | Different auth mode (`jobs_ops_access_mode`) can allow jobs token; not aligned with an Admin-only Ops console model. |
| Legacy MinerU recovery | Existing `recover-mineru-result` queries MinerU, enqueues callback processing, and can trigger download/conversion through stage dispatch. | No reason field, no explicit audit event, no dry-run/provider-call preview, and provider call happens synchronously before enqueue. |
| Legacy cleanup-local-files | Existing cleanup removes local work directory and audits reason. | No dry-run endpoint; returns local paths; should not be generalized into automated cleanup without tighter preview and path redaction. |
| Provider cancellation | No local MinerU cancellation method exists. | External support and semantics are unknown; requires primary provider documentation and fake-client tests before implementation. |
| Alert delivery | No Slack/email/webhook delivery is implemented. | Needs destination config, dry-run/test delivery, idempotency, rate limiting, escalation policy, and audit. |
| Automated cleanup execution | Current cleanup runner is read-only; physical deletion is manual selected execution. | No scheduler loop, signed cleanup plan, run history, lock, rate limit, or automated deletion policy. |

## Risk Taxonomy

| Risk class | Examples | Required gate |
| --- | --- | --- |
| Read-only | Ops alert readiness, cleanup report, action catalog. | Auth and sensitive-field redaction. |
| Metadata mutation | Archive, cancel, retry reset, mark expired. | Reason, audit, state precondition, exact target IDs. |
| Queue mutation | Retry enqueue, recovery enqueue, stage replay. | Dry-run/preview, idempotency key, stage-message precondition, audit. |
| Provider call | MinerU submit/query/download, future cancel. | Explicit `provider_call=true`, dry-run, capability check, timeout/retry policy, fake-client tests. |
| Notification delivery | Slack/email/webhook/page. | Test delivery, destination allowlist, rate limit, dedupe key, audit. |
| Destructive filesystem/object mutation | Physical delete, local cleanup, future automated cleanup. | Confirmation phrase, exact IDs, dry-run, reason, audit, batch cap, object identity re-read. |

## Recommended Next Implementation Slice

Recommended next implementation task: `ops-recovery-action-safety-registry`.

Implement an Admin-only, read-only recovery action safety registry and per-target preview contract. It should catalog available or candidate Ops actions without executing them.

The first slice should return, for each action:

- `action_id`
- `label`
- `category`
- `available`
- `target_type`
- `requires_admin`
- `requires_reason`
- `requires_confirmation`
- `dry_run_supported`
- `mutates_metadata`
- `mutates_queue`
- `calls_provider`
- `sends_notification`
- `deletes_data`
- `audit_action`
- `known_gaps`
- `suggested_route`

For a selected target, preview should return eligibility and missing gates, not execute:

- target exists / visible.
- current status allows the action.
- required reason/confirmation/provider capability state.
- expected audit action.
- provider call flag.
- destructive action flag.

This gives the Ops Dashboard a stable source of truth for what actions are safe to expose later, without prematurely implementing provider cancellation, notification delivery, or automated cleanup.

## Why Not These First

| Candidate | Decision | Reason |
| --- | --- | --- |
| Provider cancellation | Defer | Local client has no cancellation method and external provider semantics are unverified. Implementing this first risks false cancellation guarantees. |
| Alert delivery | Defer | Delivery needs destination config, dedupe/rate-limit, and audit. It should reference stable alert/action IDs first. |
| Automated cleanup execution | Defer | Highest irreversible blast radius. It must wait for signed plan/run history/lock/rate limit and should reuse existing manual physical-delete safety. |
| Direct recovery execution from Ops Dashboard | Defer | Existing recovery actions are split across `document_jobs` and legacy `jobs`; a central safety registry should normalize gates first. |
| Hardening `recover-mineru-result` immediately | Defer one slice | It is high priority, but it calls provider and enqueues processing. First define the action safety contract so hardening has a stable target shape. |

## Proposed Safety Contract

### Authorization

- New Ops action governance endpoints should be Admin-only.
- Existing user-facing document job actions can remain authenticated-user flows; the Ops console should not broaden access.
- Legacy jobs-token access should not be accepted for new Ops action governance endpoints.

### Preview and dry-run

- Every Ops action exposed from the dashboard must have a read-only preview.
- Preview must use exact target IDs.
- Preview must say whether execution would mutate metadata, queue, provider state, notification channels, or storage.
- Preview must not call providers, enqueue workers, send notifications, or delete data.

### Execution gates for future tasks

- Reason required for every mutation.
- Confirmation phrase required for irreversible, provider-side, or automated bulk actions.
- Batch caps required for any multi-target operation.
- Re-read target records immediately before execution.
- Include trace ID in state events and audit events.
- Return per-target outcomes, not only a top-level success flag.

### Provider calls

- Provider call execution must be opt-in per action and visible in preview.
- Provider cancellation must not be represented as guaranteed until the provider API and result semantics are verified.
- Provider failure must not silently mark local cancellation as provider-canceled.
- Fake provider tests must cover success, already-finished, missing upstream ID, timeout, and provider error.

### Alert delivery

- Delivery must be separate from alert computation.
- Delivery should use a dedupe key such as `{alert_code}:{target_id}:{window}`.
- Test delivery should be available before real delivery.
- Destination names may be exposed; secrets/webhook URLs must not be returned.
- Delivery attempts should be audited or recorded with bounded metadata.

### Automated cleanup

- Scheduler execution must not directly call broad delete operations.
- Automated cleanup needs run history, lock/single-flight guard, dry-run report hash, limits, and explicit policy mode.
- Destructive cleanup should reuse physical-delete eligibility and per-file outcomes.
- Read-only runner output is not delete authorization.

## Suggested Follow-up Task Map

1. `ops-recovery-action-safety-registry`
   - Admin-only read-only action registry and per-target preview.
   - No execution.
2. `legacy-mineru-recovery-governance-hardening`
   - Add reason/audit/dry-run/provider-call flag around `recover-mineru-result`.
   - Do not add provider cancellation yet.
3. `provider-cancellation-capability-spike`
   - Verify provider docs/API and define fake-client contract.
   - Decide whether cancellation can be implemented honestly.
4. `ops-alert-delivery-dry-run-governance`
   - Add test/dry-run delivery and dedupe model before real delivery.
5. `file-retention-automated-cleanup-execution-governance`
   - Add scheduler/run-history/lock only after destructive automation rules are approved.

## Review Gate

Stop here for review. Do not run `task.py start` until the user explicitly approves a concrete implementation slice.
