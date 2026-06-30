# Next-stage release and beta closure

## Goal

把当前仓库已经具备的 PDF-to-Word、P1 翻译 beta、内部门户、验收中心和运维能力收口成下一阶段可验收路线图。父任务只负责路线图、子任务边界、跨子任务验收和最终整合判断；具体实现或验证工作落在子任务中。

## Evidence Basis

- `README.md` records the current P0 Files + Document Jobs flow, P1 translation beta scope, and P2 internal operations scope.
- `docs/api/` records current API contracts for document jobs, files, health, ops, and acceptance evidence.
- `docs/dev/` records backend architecture, local/hostdzire validation boundaries, and known open issues.
- `frontend/src/router/index.ts` and `frontend/src/navigation/appShell.ts` show the internal portal route and navigation surface.
- `app/main.py`, `app/domains/document_jobs/`, `app/domains/files/`, `app/services/health_service.py`, and `app/domains/ops/` show the implemented backend capability boundary.
- `tests/` and `frontend/src/**/*.test.ts` / Playwright specs show existing test coverage.
- `.trellis/tasks/06-26-translation-provider-batching-recovery-phase-3/` is an existing in-progress task and is reused rather than duplicated.

## Child Task Map

| Child task | Priority | Purpose |
| --- | --- | --- |
| `06-29-p0-golden-sample-release-evidence-closure` | P0 | Close the latest hostdzire P0 Golden Sample evidence and admin signoff loop. |
| `06-29-acceptance-center-release-evidence-sync` | P0 | Make Acceptance Center reflect current release evidence instead of starter summaries. |
| `06-29-p1-translation-beta-formal-sample-gate` | P1 | Complete the P1 translation beta formal sample gate and regression evidence. |
| `06-26-translation-provider-batching-recovery-phase-3` | P1/P2 | Reuse the existing Phase 3 task for provider batch long-PDF validation, runbook, and operations-entry evaluation. |
| `06-29-internal-portal-core-workflow-hardening` | P1 | Validate and harden operator/admin internal portal workflows. |
| `06-29-ops-gate-and-recovery-readiness` | P2 | Turn online gate, incident triage, recovery boundaries, and runbook into operations readiness evidence. |
| `06-29-dev-docs-and-trellis-hygiene` | P2 | Remove planning noise from empty/stale dev docs and Trellis task state. |

## Parent Requirements

- R1. Do not expand product scope into SaaS, multi-tenant customer self-service, generic PDF support, online Word editing, billing, or SSO.
- R2. Treat hostdzire/staging release evidence as the source of truth for P0/P1/P2 release readiness; local tests are supporting evidence only.
- R3. Keep every child independently reviewable, testable, and archivable.
- R4. Keep the existing Phase 3 provider batch task as the single owner for provider batch validation work.
- R5. Mark user decisions explicitly when scope depends on sample ownership, batch-level write operations, or real destructive/external ops integrations.

## Cross-Task Acceptance Criteria

- [x] P0 release readiness can be judged from current Golden Sample evidence, admin signoff, and Acceptance Center latest summary.
- [x] P1 translation beta readiness can be judged from formal sample coverage, regression output, QA evidence, and any remaining blockers.
- [x] Operations readiness can be judged from online gate output, incident/recovery documentation, and explicit gated/deferred capabilities.
- [x] Internal portal workflows have evidence for operator/admin permissions, core task flow, QA, downloads, acceptance, and ops views.
- [x] Documentation and Trellis state no longer contain obvious empty/stale planning traps that would mislead the next development session.
- [x] No child implements out-of-scope batch-level write operations or destructive/external ops behavior without a separate user decision.

## Progress Update 2026-06-30

- Completed and archived children: `06-29-p0-golden-sample-release-evidence-closure`, `06-29-acceptance-center-release-evidence-sync`, `06-29-p1-translation-beta-formal-sample-gate`, `06-29-ops-gate-and-recovery-readiness`, `06-29-internal-portal-core-workflow-hardening`, `06-29-dev-docs-and-trellis-hygiene`, and `06-26-translation-provider-batching-recovery-phase-3`.
- Current computed parent progress: 7/7 children done.
- Remaining active children: none.
- Release evidence status: P0, P1, and P2 current hostdzire evidence is synced into Acceptance Center; latest summary has no blockers and retains visible warnings for P1/P2.
- Internal portal status: operator/admin workflow evidence passed local unit/build checks and relevant Playwright smoke coverage, including job lifecycle, QA, downloads, forbidden states, users, configuration, audit logs, file retention, Acceptance Center, system status, and ops dashboard.
- Docs/Trellis hygiene status: empty `docs/dev` placeholders are now explicitly marked deferred, the backend dev-docs index uses repository-relative current links, and the stale `00-bootstrap-guidelines` task has been archived.
- Provider batch Phase 3 status: batch-aware P1 reporting helpers, provider batch runbook guidance, and operations-entry evaluation are present in the repository; task scope remained read-only/reporting-only, with batch-level write operations still design-only and gated behind future user decisions.

## User Decisions Needed

- Resolved: source and acceptability standard for the two missing P1 real English datasheet samples.
- Whether batch-level retry/cancel/requeue/finalizer write operations should enter a later implementation task.
- Whether real S3 deletion, automatic cleanup scheduler, provider cancellation, or external alert delivery should move from gated/deferred to implementation scope.

## Out Of Scope

- Direct business-code implementation in this parent task.
- Creating new product surfaces not grounded in the current README, docs, code, tests, or existing Trellis tasks.
- Replacing the existing Phase 3 task with a duplicate provider batch task.
