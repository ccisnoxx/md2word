# Phase 7 Controlled Real Integration Rollout Planning Design

## Decision

Proceed with Phase 7 as controlled rollout planning, not execution.

Recommended Phase 7 minimum closed loop: `slack-webhook-delivery-pilot`.

Rationale:

- It is the lowest-risk real external action among the remaining candidates because it does not intentionally mutate local product state or delete customer data.
- Phase 6 already completed `integration-control-plane` and `real-alert-delivery-adapter-contract`, so the remaining planning gap is rollout control: approved destination, secret-ref setup, allowlist, rate limit, confirmation phrase, rollback, and live-send approval.
- It can exercise the shared control-plane, adapter result, audit details, idempotency, timeout, and rollback model before destructive execution is considered.

Keep `real-s3-delete-guarded-execution` as a separate destructive controlled rollout. It must not be bundled into the Slack/webhook pilot or used as the first Phase 7 closed loop.

Keep `cleanup-scheduler-controlled-execute` behind accepted guarded real S3 deletion. Scheduler execute must not be planned as an independent first destructive path.

Keep `real-provider-cancellation-adapter` blocked. The accepted Phase 6 semantics decision is `unsupported_by_public_docs`; implementation or rollout can reopen only if primary provider evidence changes or a private provider contract is approved.

## Rollout Lane Map

| Lane | Phase 7 Classification | Risk | Dependency | Planning Outcome |
| --- | --- | --- | --- | --- |
| `slack-webhook-delivery-pilot` | Recommended first minimum closed loop | Medium external side effect | `real-alert-delivery-adapter-contract` | Plan first controlled rollout; no live send in this task. |
| `real-s3-delete-guarded-execution` | Separate destructive rollout | High destructive data risk | `s3-delete-localstack-contract` | Plan separately with exact-target, signed-plan, audit/history, metadata mutation, and rollback gates. |
| `cleanup-scheduler-controlled-execute` | Phase 7+ dependent rollout | High autonomous destructive risk | Accepted `real-s3-delete-guarded-execution` | Defer until real S3 delete acceptance exists; never first destructive path. |
| `real-provider-cancellation-adapter` | Blocked | High provider semantics risk | Provider evidence change or private contract | Do not plan implementation while current evidence remains `unsupported_by_public_docs`. |

## Future Task Boundaries

### 1. `phase7-slack-webhook-delivery-pilot`

Purpose: implement and verify one real alert delivery pilot after user approval of external setup and live-send scope.

Minimum rollout requirements:

- One approved test Slack/webhook destination.
- Secret referenced by `secret_ref`; no secret value in settings JSON, API response, audit details, history, logs, or frontend state.
- Destination allowlist and exact destination id.
- Exact `alert_codes`; no implicit all-alert delivery.
- Capability flag disabled by default, dry-run/preview retained, kill switch active path verified.
- Explicit confirmation phrase for live send.
- Bounded provider timeout and no unbounded retry loop.
- Stable idempotency key and dedupe window.
- Rate limit for repeated manual attempts.
- Structured audit details with gate snapshot, adapter mode, contract version, target, idempotency key, outcome, provider-call boolean, timeout, and non-sensitive external id.
- Rollback plan: disable capability, activate kill switch, remove destination allowlist entry, rotate or remove secret ref, inspect audit/history.

Explicit non-scope for this future task:

- No email rollout unless separately approved.
- No broad webhook destination set.
- No provider cancellation.
- No object deletion.
- No scheduler execute.

### 2. `phase7-real-s3-delete-guarded-rollout-planning`

Purpose: separately design the destructive real S3 delete rollout before any implementation or execution.

Minimum planning requirements:

- Exact bucket/key and optional version id per target.
- Expected ETag or equivalent optimistic guard where available.
- Signed cleanup plan or equivalent signed deletion plan with preview hash.
- Idempotency model for `deleted`, `already_missing`, version mismatch, failure, and timeout.
- Metadata mutation rule: mark local metadata deleted only after accepted provider success or proven idempotent already-missing result.
- Audit/history schema with gate snapshot and provider request id redaction rules.
- Rollback and incident handling for partial deletion, metadata mutation failure, and delete-provider timeout.
- Manual one-target pilot before any batch execution.
- User approval for destructive execution in a future task.

Explicit non-scope:

- No scheduler execute.
- No delete-all or prefix-wide delete.
- No autonomous execution.
- No LocalStack delete in this current planning task.

### 3. `phase7-cleanup-scheduler-controlled-execute-planning`

Purpose: plan disabled-by-default scheduler execute only after accepted guarded real S3 deletion evidence exists.

Hard dependency:

- Must cite acceptance evidence from `real-s3-delete-guarded-execution`.

Minimum planning requirements:

- Scheduler execute remains disabled by default.
- Existing dry-run and history remain the default operator path.
- Per-file eligibility, signed plan, preview hash, cleanup lock, bounded batch size, retry limits, and failure history are mandatory.
- Scheduler must call the same guarded delete path as manual execution; it must not bypass exact-target or signed-plan gates.
- Rollout must start with a no-op/dry-run schedule and explicit manual promotion.

### 4. `phase7-provider-cancellation-evidence-watch`

Purpose: track provider evidence only if the provider contract changes.

Current decision:

- Do not implement `real-provider-cancellation-adapter`.
- Do not run real provider cancellation.
- Do not treat local job cancellation as provider cancellation.
- Reopen only with primary provider cancellation docs/API evidence or an approved private provider contract.

## Shared Phase 7 Approval Gates

Every future real-execution task must include:

- Capability-specific enable flag and kill switch.
- Admin-only execution endpoint or explicitly approved operator role.
- Exact target selection.
- Explicit reason and confirmation phrase.
- Preview/dry-run path before live execution.
- Stable idempotency key and dedupe behavior.
- Bounded timeout and retry policy.
- Structured audit details and durable history.
- Secret redaction and provider response body redaction.
- Rollback procedure and kill-switch verification.
- Focused tests proving blocked/default behavior before live execution is reachable.
- A separate user approval step before any real provider call, real external send, real delete, LocalStack delete, scheduler execute, or conversion main-flow run.

## Planning Status

This task creates only the Phase 7 planning artifacts. It does not activate the Trellis task, implement code, run tests that exercise external/destructive behavior, or perform git operations.
