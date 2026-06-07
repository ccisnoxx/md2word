# Phase 7 Controlled Real Integration Rollout Planning Implementation Plan

## Task Classification

Planning/design only. No product implementation or real execution is included in this task.

## Completed Planning Work

- [x] Read `AGENTS.md`.
- [x] Read `.trellis/workflow.md`.
- [x] Read `.codestable/attention.md`.
- [x] Read Phase 6 closeout acceptance.
- [x] Read CodeStable real-integration readiness roadmap and items.
- [x] Create Trellis planning task `phase7-controlled-real-integration-rollout-planning`.
- [x] Document Phase 7 requirements and non-goals in `prd.md`.
- [x] Document controlled rollout lane decisions in `design.md`.
- [x] Keep the task in `planning` status; do not run `task.py start`.
- [x] Run Trellis task validation for context manifests only.

## Future Task Plan

1. `phase7-slack-webhook-delivery-pilot`
   - Classification: controlled external-send rollout.
   - Dependency: Phase 6 `real-alert-delivery-adapter-contract`.
   - Start condition: user approves test destination, secret-ref setup, allowlist, confirmation phrase, rate limit, rollback plan, and live-send scope.
   - Verification target: blocked-by-default behavior, dry-run/preview, exact destination, idempotency/dedupe, timeout/error handling, audit/history, kill-switch rollback, and one approved live-send smoke only after explicit approval.

2. `phase7-real-s3-delete-guarded-rollout-planning`
   - Classification: destructive controlled rollout planning.
   - Dependency: Phase 6 `s3-delete-localstack-contract`.
   - Start condition: user explicitly approves destructive planning scope.
   - Verification target before execution: exact target, signed plan, idempotency, audit/history, metadata mutation contract, rollback, and one-target manual pilot design.

3. `phase7-cleanup-scheduler-controlled-execute-planning`
   - Classification: dependent autonomous destructive rollout planning.
   - Dependency: accepted real S3 delete guarded execution.
   - Start condition: cite real S3 delete acceptance evidence.
   - Verification target before execution: scheduler uses the same guarded delete path, remains disabled by default, respects lock/history/signed-plan/batch bounds, and cannot bypass per-file eligibility.

4. `phase7-provider-cancellation-evidence-watch`
   - Classification: blocked evidence tracking only.
   - Dependency: provider evidence changes or private provider contract approval.
   - Start condition: primary provider docs/API evidence or approved private contract contradicts the current `unsupported_by_public_docs` decision.
   - Verification target before implementation: supported operation id, idempotency model, terminal-state semantics, timeout/error contract, and no automatic local job mutation.

## Guardrails For This Planning Task

- Do not run real Slack/webhook delivery.
- Do not run real provider cancellation.
- Do not run real S3 deletion.
- Do not run LocalStack deletion.
- Do not run scheduler execute.
- Do not run conversion main flow, MinerU parsing/recovery, translation provider calls, or Word generation.
- Do not stage, commit, push, branch switch, revert, or destructively clean files.
- Do not mutate product source code in this task.

## Validation For This Planning Task

- Completed: `python3 ./.trellis/scripts/task.py validate 06-08-phase7-controlled-real-integration-rollout-planning`.
- Result: passed; `implement.jsonl` and `check.jsonl` each contain 6 valid entries.
- Do not run backend tests, frontend build, OpenAPI export, provider calls, S3 calls, LocalStack calls, scheduler loops, or conversion workflows for this planning-only task.

## Residual Risks

- Future live Slack/webhook pilot still requires external destination and secret-ref approval that this task does not provide.
- Real S3 delete remains destructive and needs a separate approval path with stricter review than alert delivery.
- Scheduler execute remains unsafe to plan as runnable until guarded real S3 delete acceptance exists.
- Provider cancellation remains unsupported by current public provider evidence.
