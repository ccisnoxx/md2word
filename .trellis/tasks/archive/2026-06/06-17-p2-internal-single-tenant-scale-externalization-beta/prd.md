# P2 internal single-tenant scale externalization beta

## Goal

Bring md2word from P0/P1 beta evidence into an internally deliverable, maintainable, single-tenant production workflow. P2 must make hostdzire deployment repeatable, observable, recoverable, and verifiable for internal operators/admins while keeping the product focused on technical datasheets and electronics documents.

## What I already know

- P0 Word delivery quality beta has hostdzire evidence showing 4/4 Golden Sample success and admin signoff, with the task artifact as the authoritative release evidence.
- P1 translation QA/governance implementation and hostdzire smoke path are complete; formal `p1_beta_ready=true` still needs three real samples and admin signoff, which is treated as a separate admin validation gate unless explicitly made a P2 blocker.
- Production/semi-production baseline remains MySQL metadata, Redis/Celery, Docker Compose, and a single document worker on hostdzire.
- dmit remains the public front machine. Ordinary P2 code, deployment, and validation changes target hostdzire.
- Local development must not start the frontend/backend, local Docker runtime, MySQL, Redis/Celery, worker, Playwright smoke, or full conversion chain.
- Complete chain validation follows the online-first flow: local edit/checks, upload to hostdzire, deploy, verify against the online MySQL + Celery environment.
- Current frontend already has internal portal pages for jobs, upload, job detail, translation QA, system status, ops dashboard, audit events, and file retention.
- Current backend already has document jobs, health/metrics/ops-alerts, admin recovery actions, audit, file retention, and integration control plane surfaces.
- The working tree contains many pre-existing P0/P1 changes. P2 work must keep its own task evidence clear and avoid claiming unrelated dirty files as P2 implementation.

## Requirements

1. P1/P0 evidence closeout
   - Record the P1 completion stance: implementation and hostdzire smoke are complete; formal P1 beta signoff remains an admin-sample gate.
   - Identify and fix or explicitly supersede stale docs that contradict the P0 hostdzire signoff.
   - Keep P2 from reworking P0 renderer quality or P1 translation QA semantics.

2. P2 release readiness and evidence gate
   - Provide a repeatable P2 online gate that collects runtime readiness, metrics, ops alerts, release check results, and P0/P1 preflight status into a saved evidence bundle.
   - The gate must run against hostdzire and must not require local MySQL/Redis/API/frontend services.
   - The gate must distinguish preflight/smoke evidence from formal P0/P1 quality signoff.

3. Deployment traceability
   - Surface deployment identity in runtime health/metrics or equivalent evidence: app name, environment, deployment mode, version or deployment id, and process start time.
   - Document how the deployment id is set on hostdzire without committing secrets or host credentials.

4. Internal operations experience
   - System Status and Ops Dashboard should make readiness blockers, worker/backend baseline, queue pressure, stale/timed-out jobs, callbacks, and storage capacity easy for admins to inspect.
   - Admin recovery actions must remain gated, previewable where applicable, audited when executed, and limited to the existing safe MVP scope.
   - Operator/admin task actions should continue to use existing permissions and available-actions contracts.

5. Capacity and data-safety governance
   - P2 must provide a practical internal capacity workflow: storage visibility, retention preview/dry-run, quota status, backup/rollback guidance, and evidence collection.
   - Dangerous cleanup or deletion must not become silent or automatic in P2.

6. Documentation and rollout
   - Update README/runbooks/deploy docs to describe P2 internal single-tenant release and validation.
   - Add P2 acceptance evidence under this task after local checks and hostdzire verification.
   - Keep hostdzire/dmit roles explicit.

## Acceptance Criteria

- [ ] A P2 task PRD, current-state research, and implementation/check context exist under `.trellis/tasks/06-17-p2-internal-single-tenant-scale-externalization-beta/`.
- [ ] P0/P1 evidence status is documented without contradictory release conclusions.
- [ ] Runtime health/metrics or release evidence includes deployment traceability fields useful for hostdzire validation.
- [ ] A P2 online gate script or equivalent documented command produces a versioned report under `tests/tmp/p2_online_runs/<run_id>/`.
- [ ] P2 gate checks hostdzire runtime readiness, MySQL + Celery baseline, ops alerts, and P0/P1 preflight status without rerunning P0/P1 formal quality gates by default.
- [ ] Admin-facing frontend surfaces any new P2 readiness/capacity/governance fields without exposing secrets or full document text.
- [ ] All admin execution paths touched by P2 remain permission-gated and audited.
- [ ] Local verification uses only no-service checks: static checks, unit tests, type checks, OpenAPI/export checks, and script dry-run/argument checks.
- [ ] Hostdzire verification follows the online-first flow and records evidence in this task.

## Definition of Done

- P2 changes are implemented and documented.
- Local no-service verification has been run and recorded.
- Changes are uploaded to hostdzire, deployed against the MySQL + Celery baseline, and verified online.
- P2 acceptance evidence and remaining risks are written to this task directory.
- Any spec update decision is recorded.
- P2 changes are kept separate from pre-existing dirty P0/P1 work as far as the worktree allows.

## Technical Approach

Use existing control surfaces before adding new ones:

- Extend existing health/metrics/readiness data for deployment traceability instead of creating a parallel status API.
- Add a small P2 online evidence script that composes existing endpoints and existing release/preflight checks.
- Prefer frontend additions to System Status/Ops Dashboard/File Retention over new top-level pages.
- Reuse existing ops recovery, audit, retention, and document-job available-actions contracts.
- Keep database schema stable for P2 unless a verified blocker requires a targeted change.

## Decision (ADR-lite)

**Context**: P2 asks for scale and externalization, but the product is still internal, single-tenant, and single-worker. The codebase already contains substantial health, ops, audit, retention, and task governance infrastructure.

**Decision**: P2 will be an operationalization and release-readiness layer, not a platform rewrite. It will add deployment traceability, an online evidence gate, runbook clarity, and small frontend/backend visibility improvements while avoiding multi-worker, SaaS, and destructive automation.

**Consequences**: This keeps the scope small enough to finish and verify on hostdzire. Large-scale query optimization, real alerting, real S3 delete, autonomous cleanup, and SSO remain explicit later-stage work.

## Out of Scope

- Generic PDF support.
- P0 renderer quality changes or Golden Sample threshold changes.
- P1 translation QA workflow redesign.
- SaaS multi-tenant isolation, public registration, billing, public customer portal, or SSO.
- Multi-worker/distributed task platform.
- Real provider cancellation, real S3 deletion, autonomous cleanup scheduler, or destructive automatic retention execution.
- Prometheus/OpenTelemetry stack, unless added later as a separate ops task.

## Implementation Plan

1. Close planning artifacts
   - Write current-state research.
   - Curate Trellis implementation/check context.
   - Start the task.

2. Release traceability and P2 online gate
   - Add deployment metadata to runtime health/metrics evidence.
   - Add a P2 gate script that collects live/ready/metrics/ops-alerts/release-check/preflight evidence from a supplied runtime URL.
   - Add tests for no-service report building and failure classification.

3. Frontend/internal ops visibility
   - Update System Status/Ops Dashboard to show deployment metadata and P2 gate-relevant readiness/capacity status.
   - Keep all execution controls admin-only and reuse current ops APIs.

4. Docs and evidence
   - Update README, deploy/runbook docs, and stale P0/P1 status notes.
   - Add P2 acceptance audit template and fill local verification.

5. Online verification
   - Upload to hostdzire with rsync dry-run first.
   - Deploy Docker Compose on hostdzire.
   - Run the P2 online gate plus required runtime checks.
   - Record final evidence and remaining risks.

## Validation Plan

Local:

- `git diff --check`
- targeted Python unit tests for changed backend/script behavior
- `python scripts/ops/check_release.py`
- `cd frontend && npx vue-tsc --noEmit` when frontend changes
- `cd frontend && npm run test:unit` when frontend logic changes

Hostdzire:

- `curl` live/ready/metrics on `http://127.0.0.1:${MD2WORD_API_BIND_PORT:-18000}`
- `scripts/ops/check_release.py --runtime-url ...`
- P0 Golden Sample preflight only by default
- P1 translation preflight only by default
- P2 online gate report saved under `tests/tmp/p2_online_runs/<run_id>/`
- public dmit entry live/ready checks via `https://md2word.962850.xyz`

## Research References

- [`research/current-state.md`](research/current-state.md) - current implementation map and P2 scope constraints.
