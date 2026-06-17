# P2 current-state research

## Scope constraints

- Product scope is technical datasheets / electronics documents only.
- P2 externalization means internal single-tenant delivery, deployment, and maintainability. It does not mean SaaS, public registration, billing, multi-tenant organizations, or generic PDF.
- Production target is hostdzire with Docker Compose, MySQL metadata, Redis/Celery, and one document worker.
- dmit is only the public front machine and should not be changed for ordinary P2 updates.
- Local development must not start local frontend/backend services or connect to local MySQL/Redis.

## Authoritative evidence read

- `README.md`
- `docs/deploy/online-first-validation-workflow.md`
- `docs/deploy/hostdzire-dmit-md2word.md`
- `docs/deploy/p0-docker-deployment.md`
- `docs/runbooks/backend.md`
- `docs/runbooks/internal-portal.md`
- `.trellis/tasks/06-16-p0-word-delivery-quality-beta/acceptance-audit.md`
- `.trellis/tasks/06-16-p0-word-delivery-quality-beta/artifacts/hostdzire-golden-sample-20260617T053003Z/report.md`
- `.trellis/tasks/06-17-p1-translation-qa-governance-beta/prd.md`
- `.trellis/tasks/06-17-p1-translation-qa-governance-beta/acceptance-audit.md`
- `app/services/health_service.py`
- `app/domains/ops/router.py`
- `frontend/src/pages/SystemStatusPage.vue`
- `frontend/src/pages/OpsDashboardPage.vue`
- `scripts/ops/check_release.py`
- `scripts/ops/run_golden_sample_regression.py`
- `scripts/ops/run_p1_translation_regression.py`

## Current backend surfaces

- `HealthService` already builds readiness, dependency checks, runtime metrics, and ops alert signals.
- Readiness already reports MySQL/Celery baseline fields including `effective_repository_backend`, `document_jobs_worker_backend`, `p0_document_jobs_ready`, callback counts, stale jobs, and resource versions.
- Ops APIs are admin-only and include integration capability reporting, recovery-action registry/preview/execute, alert dry-run/fake send, Slack pilot gates, S3 delete contract, and provider-cancellation evidence.
- `document_job.replay_execution` is the only currently executable recovery action through the ops execute endpoint.
- Audit recording exists for recovery execution and real alert delivery.
- File retention and quota-related APIs/pages exist, with safe preview/dry-run style controls.

## Current frontend surfaces

- `SystemStatusPage.vue` reads `/health/ready` and `/health/metrics`, then displays readiness, backend, worker, storage, task/queue, callback, and resource-version state.
- `OpsDashboardPage.vue` reads ops alerts, integration capabilities, recovery actions, and alert delivery state. The page message emphasizes safe operations and blocked real integrations.
- Jobs pages already provide upload, mode selection, status filtering, batch actions, detail diagnostics, events, files, QA links, retry/clone/cancel/archive/delete flows.
- `FileRetentionPage.vue` and `AuditLogPage.vue` are already routed under system status for admin use.

## Current deployment and validation surfaces

- `docker/prod/docker-compose.yml` runs API, worker, Redis, and MySQL. The frontend is served by nginx from a static path outside the Compose app image.
- `docs/deploy/online-first-validation-workflow.md` is the canonical local-edit -> hostdzire-upload -> online-verify process.
- `scripts/ops/check_release.py` performs no-service release checks and can optionally validate a running API readiness URL.
- P0 and P1 have dedicated online regression/preflight scripts. P2 should call their preflight modes by default, not their formal quality gates.

## Gaps for P2 MVP

- Runtime evidence does not clearly expose deployment identity such as a deployment id, version label, or process start time.
- There is no P2-specific online gate report that composes health, metrics, ops alerts, release check, P0 preflight, and P1 preflight into one artifact.
- Existing frontend status pages can show most data, but not deployment traceability or P2 release-gate framing.
- Deployment docs describe the online-first workflow but do not yet name P2 internal single-tenant acceptance as a standalone gate.
- A stale P0 test report still says Golden Sample status is blocked even though task-level hostdzire evidence says P0 is signed off.
- P1 implementation/smoke is complete, but formal beta signoff is not complete because only one available real sample exists.

## Recommended P2 implementation boundary

- Add deployment metadata fields to existing health/metrics contracts.
- Add a P2 online gate script under `scripts/ops/` and tests for report assembly.
- Update System Status/Ops Dashboard to surface deployment metadata and P2 gate-relevant states.
- Update deploy/runbook docs and task acceptance evidence.
- Do not add tables, background schedulers, provider integrations, multi-worker coordination, or new public-facing product flows.

## Risks

- The working tree includes many pre-existing P0/P1 dirty files; P2 implementation must track files touched this session carefully.
- Hostdzire verification needs credentials and online environment access, which cannot be proven by local tests.
- If P2 touches shared health schemas, OpenAPI and frontend API types must be kept in sync.
- If the expected internal job volume is much larger than low thousands, MySQL list/filter query optimization may become a follow-up requirement rather than part of P2 MVP.
