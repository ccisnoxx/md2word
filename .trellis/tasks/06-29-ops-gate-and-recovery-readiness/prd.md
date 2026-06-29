# Ops gate and recovery readiness

## Goal

把 P2 online gate、incident triage、恢复边界和 runbook 整理成可执行的运维 readiness 检查，明确哪些能力已经可用、哪些仍是 gated/deferred。

## Evidence

- `README.md` defines P2 as internal single-tenant scale-out and operations readiness, not SaaS expansion.
- `docs/deploy/online-first-validation-workflow.md` defines hostdzire online-first validation and P2 online gate shape.
- `docs/api/ops.md` says the ops namespace is mostly read-only/gated and does not execute real provider calls, destructive cleanup, or Word generation.
- `docs/api/files.md` documents file retention/quota dry-run and protected physical delete boundaries.
- `app/domains/document_jobs/incidents.py` and `frontend/src/pages/OpsDashboardPage.vue` show existing incident and ops surfaces.

## Requirements

- R1. Treat online gate output as the main P2 readiness artifact.
- R2. Cover ready, metrics, ops alerts, release check, P0 preflight, and P1 preflight where available.
- R3. Keep destructive/external capabilities gated unless the user explicitly moves them into implementation scope.
- R4. Document recovery and escalation paths for failed, stalled, artifact-missing, translation-failed, and conversion-failed jobs.
- R5. Keep redaction and audit boundaries explicit for ops evidence.

## Acceptance Criteria

- [ ] Online gate output reports ready, metrics, ops alerts, release check, P0 preflight, and P1 preflight status with blockers/warnings.
- [ ] Incident triage can identify failed, stalled, artifact_missing, translation_failed, conversion_failed, and timeout-style cases with job links.
- [ ] Runbook documents allowed recovery actions and clearly marks gated/deferred actions.
- [ ] Destructive or external operations remain dry-run/preview/gated unless separately approved by the user.
- [ ] Operations evidence can be registered or referenced by Acceptance Center without storing secrets, signed URLs, full text, or binary artifacts.

## User Decision Needed

- The user must decide whether real S3 deletion, automatic cleanup scheduler, provider cancellation, and external alert delivery should remain deferred or move into a later implementation task.

## Out Of Scope

- Implementing real destructive/external integrations by default.
- Adding SaaS, multi-tenant capacity management, billing, or external customer operations.
- Replacing existing health/metrics/ops endpoints wholesale.
