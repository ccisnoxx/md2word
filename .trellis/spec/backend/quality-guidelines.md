# Quality Guidelines

> Code quality standards for backend development.

---

## Overview

<!--
Document your project's quality standards here.

Questions to answer:
- What patterns are forbidden?
- What linting rules do you enforce?
- What are your testing requirements?
- What code review standards apply?
-->

(To be filled by the team)

---

## Forbidden Patterns

<!-- Patterns that should never be used and why -->

(To be filled by the team)

---

## Required Patterns

<!-- Patterns that must always be used -->

### Scenario: Online health and release gates

#### 1. Scope / Trigger

- Trigger: any change that affects `/api/v1/health/ready`, `/api/v1/health/metrics`, deployment env wiring, release validation scripts, or hostdzire production-like validation.
- Scope: internal single-tenant deployment only. Do not add SaaS tenant, billing, registration, or generic PDF behavior as part of this gate.

#### 2. Signatures

- API: `GET /api/v1/health/ready`
- API: `GET /api/v1/health/metrics`
- Command: `scripts/ops/run_p2_online_gate.py`
- Env keys:
  - `APP_VERSION`: non-secret release label, default `dev`.
  - `DEPLOYMENT_ID`: non-secret deployment trace id, optional but expected on hostdzire.
  - `P2_ONLINE_BASE_URL`: backend base URL for the online gate.
  - `P2_ONLINE_PUBLIC_URL`: optional public entry URL for dmit -> hostdzire checks.
  - `P2_ONLINE_USERNAME` / `P2_ONLINE_PASSWORD` or `P2_ONLINE_BEARER_TOKEN`: admin credential source for P0/P1 preflight checks.

#### 3. Contracts

- Health `deployment` response object:
  - `environment: str`
  - `public_deployment_mode: str`
  - `version: str`
  - `deployment_id: str`
  - `started_at: datetime`
- Hostdzire readiness baseline:
  - `effective_repository_backend == "mysql"`
  - `document_jobs_worker_backend == "celery"`
  - `deployment_init_ready == true`
  - `p0_document_jobs_ready == true`
  - `readiness_blockers == []`
- P2 gate reports must be written under `tests/tmp/p2_online_runs/<run_id>/report.json` and `report.md`.
- Report config may include usernames and boolean `*_configured` fields, but must redact bearer tokens and never write passwords, private keys, `.env`, or internal user file contents.

#### 4. Validation & Error Matrix

- Missing or unreachable `P2_ONLINE_BASE_URL` -> blocker.
- `/health/ready` status not ok or has readiness blockers -> blocker.
- MySQL/Celery baseline not active on hostdzire -> blocker.
- Critical ops alert present -> blocker.
- P0 or P1 preflight fails -> blocker unless explicitly skipped with a documented reason.
- Missing `APP_VERSION` or `DEPLOYMENT_ID` on hostdzire -> warning, not blocker.
- Existing failed document-job count -> warning unless paired with a critical ops alert.

#### 5. Good/Base/Bad Cases

- Good: hostdzire reports MySQL + Celery, deployment metadata is populated, public health checks pass, and P2 gate has `p2_online_gate_ready=true`.
- Base: local no-service unit/type/OpenAPI checks pass before upload; complete chain validation happens only after upload to hostdzire.
- Bad: adding a new local-only smoke check and treating it as production readiness, or hiding a failing remote preflight behind a silent fallback.

#### 6. Tests Required

- Unit tests assert the health deployment object is present in ready and metrics responses.
- OpenAPI export/check must be regenerated after response schema changes.
- P2 gate must have a mocked HTTP test covering report assembly and blocker/warning output.
- Frontend typecheck must pass after adding or changing health response fields.
- Online validation must include hostdzire `/health/live`, `/health/ready`, `/health/metrics`, ops alerts, P0 preflight, P1 preflight, and public entry checks when a public URL is configured.

#### 7. Wrong vs Correct

Wrong:

```bash
# Treats a local-only check as production readiness and skips hostdzire.
npm run test:smoke
```

Correct:

```bash
P2_ONLINE_BASE_URL="http://127.0.0.1:${MD2WORD_API_BIND_PORT:-18000}" \
P2_ONLINE_PUBLIC_URL="https://md2word.962850.xyz" \
P2_ONLINE_USERNAME=admin \
P2_ONLINE_PASSWORD='<admin-password>' \
python scripts/ops/run_p2_online_gate.py
```

---

## Testing Requirements

<!-- What level of testing is expected -->

(To be filled by the team)

---

## Code Review Checklist

<!-- What reviewers should check -->

(To be filled by the team)
