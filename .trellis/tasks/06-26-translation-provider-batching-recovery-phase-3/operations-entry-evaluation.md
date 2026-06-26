# Operations Entry Evaluation

## Decision

Phase 3 MVP should not implement a new Operations Cockpit aggregation entry or a new batch-level operations page.

Keep Job Detail as the authoritative provider batch diagnostics surface, and use existing Incident Triage / Operations Cockpit deep links to route operators into Job Detail when a job needs batch-level inspection.

## Evidence

- Job Detail already renders the “Provider 批次” diagnostics section and consumes `GET /api/v1/document-jobs/{job_id}/translation-batches`.
- Incident Triage already groups failed, stalled, retryable, and `translation_failed` document jobs, and links each row to Job Detail.
- Operations Cockpit already previews incidents, translation QA, and failed/active jobs through existing saved-view routes.
- Phase 2 explicitly deferred Incident Triage / Operations Cockpit aggregation and batch-level write operations.
- Phase 3’s confirmed MVP is production/staging validation, runbook, and evaluation; batch-level write operations are design-only.

## Current Operator Flow

1. Operator sees a failed/stalled translation job in Incident Triage or Operations Cockpit.
2. Operator opens Job Detail.
3. Operator uses the “诊断” tab and “Provider 批次” section to inspect batch status, page ranges, attempts, `finish_reason`, errors, and AI call log file ids.
4. Operator uses only task-level actions exposed by `available_actions`, such as retry/cancel/archive/clone/download.
5. If current leaf batches are inconsistent with job state, operator escalates with job id, generation, batch ids, page ranges, attempts, `finish_reason`, error summary, and trace/event context.

## Why No New Aggregation Now

A cross-job provider batch aggregation endpoint would introduce a second operational summary over the same batch records. That is useful only if operators need to detect fleet-level provider batch patterns, such as repeated truncation across jobs or many jobs stuck in finalization.

The immediate risk is not discoverability across many jobs; it is proving that the long-PDF recovery path works in a real/staging environment and documenting how to diagnose one job accurately. Existing Incident Triage and Operations Cockpit already surface the job-level failure/stall cases that lead to Job Detail.

## Future Aggregation Triggers

Reopen an Operations Cockpit / Incident Triage aggregation task if production validation or incidents show any of these patterns:

- multiple active translation jobs stuck in `queued` / `running` provider batches;
- repeated `finish_reason=length` or `truncation_retry=true` across unrelated jobs;
- jobs where all current leaf batches succeeded but finalizer/fan-in did not advance the job;
- operators repeatedly need to compare provider batch health across jobs before choosing a task-level retry;
- incident rows need batch-derived priority, such as “failed leaf batch exhausted retry” versus generic `translation_failed`.

## Future Aggregation Shape

If reopened, prefer a read-only aggregation first:

- Backend: a job-scoped or incident-scoped summary projection over existing translation batch records.
- Frontend: a compact badge/count on Incident Triage rows or Operations Cockpit preview rows.
- Navigation: deep-link to Job Detail diagnostics rather than duplicating the full batch table.
- Redaction: no prompt, response, source text, translated text, debug archive content, object storage location, signed URL, or secret value.

## Batch-Level Write Operation Design Boundary

Batch-level retry/cancel/requeue/finalizer should remain out of Phase 3 implementation. A future design must answer these before any endpoint or UI button exists:

- Permissions: admin-only or operator-visible with confirmation; exact required permission.
- Target: exact `job_id`, `generation`, `batch_id`, and current expected status.
- Idempotency: request idempotency key and duplicate request behavior.
- State safety: compare-and-set updates, stale generation rejection, terminal job rejection, and leaf/parent batch rules.
- Queue safety: whether the action mutates queue state, enqueues work, or only marks metadata.
- Audit: stable audit action, reason, actor, target, before/after status, and safety flags.
- Preview: dry-run response showing eligibility, missing gates, risk flags, and no mutation.
- Rollback: kill switch and recovery path if an operator action produces conflicting batch state.
- Redaction: response body and audit details must not include prompt/response/source/translated text or secret values.

## Current Recommendation

Ship Phase 3 with script-level batch diagnostics evidence, the backend runbook, and this evaluation. Defer provider batch aggregation and write operations until real validation shows that single-job Job Detail diagnostics plus existing incident routing are insufficient.
