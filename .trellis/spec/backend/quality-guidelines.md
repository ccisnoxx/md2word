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

### Scenario: Word template document vs page style configuration

#### 1. Scope / Trigger

- Trigger: any change that touches Word template document management, layout YAML editing, template version creation, admin settings routes, or document-job template resolution.
- Keep two product surfaces separate:
  - Word template document management owns DOCX files, company logo/default header content in the DOCX, validation jobs, publish, and default-version lifecycle.
  - Word page style configuration owns visual editing of output styles from `resources/template_configs/datasheet_template.yaml` groups.

#### 2. Signatures

- API: `GET /api/v1/templates/{template_id}/layout-config`
- API: `POST /api/v1/templates/{template_id}/layout-config/versions`
- Frontend route: `/settings/templates` and `/settings/templates/{template_id}` for template documents.
- Frontend route: `/settings/word-page-styles` and `/settings/word-page-styles/{template_id}` for page styles.

#### 3. Contracts

- Both layout-config APIs require `require_admin_actor`; non-admin users must not read or write layout config through API or see frontend entry points.
- `GET /layout-config` response fields:
  - `meta`: readonly YAML metadata such as `schema_version`, `template_name`, and `output_filename`.
  - `config`: editable layout groups only, keyed by YAML top-level groups such as `page_setup`, `heading1`, `normal`, `table_style`, `header`, and `footer`.
  - `field_schema`: backend-owned allowlist with field `type`, Chinese `label`, optional `unit`, and optional `readonly`.
- `POST /layout-config/versions` request body is `{ "config": <editable layout groups> }`.
- Saving page styles creates a draft Template Version by copying the current DOCX template file and writing a versioned `layout_config.yaml`; it must not mutate the source repository YAML directly.
- `schema_version`, `template_name`, `output_filename`, and `sample_content` are not editable style fields.
- `header.logo_path` may exist in backend config for compatibility but is readonly UI-wise; company logo/default header content belongs to the template document surface.

#### 4. Validation & Error Matrix

- Non-admin actor -> `403`.
- Missing template or missing layout YAML -> `404`.
- Non-object `config` -> `400`.
- Submitted readonly metadata (`schema_version`, `template_name`, `output_filename`) -> `400`.
- Unknown top-level group or unknown field -> `400`.
- Missing required group or field -> `400`.
- Invalid field type, alignment outside `left/center/right/justify`, invalid RGB color, negative number except indent fields -> `400`.
- Versioning backend unavailable -> `503`.

#### 5. Good/Base/Bad Cases

- Good: admin changes `heading1.font_size`, backend validates against `field_schema`, creates a draft version, and later publish/default actions make future Word generation use that version.
- Base: readonly metadata appears as status context only; frontend submits `config` groups without `sample_content`.
- Bad: exposing a raw YAML editor, combining DOCX logo/header editing with page style controls, or letting the frontend define its own allowlist independent of backend schema.

#### 6. Tests Required

- Backend tests assert admin-only access for both layout-config endpoints.
- Backend tests assert draft layout saves do not mutate the source YAML and reject unknown/readonly fields.
- Frontend smoke or unit coverage must assert non-admin routes are forbidden, template document pages do not show page-style form groups, and page-style pages hide `header.logo_path`.
- Document generation tests must cover that published/default Template Version layout config is the path resolved for later Word jobs.

#### 7. Wrong vs Correct

Wrong:

```json
{
  "schema_version": "template-config/v1",
  "sample_content": { "normal_text": "demo" },
  "heading1": { "font_size": 14 }
}
```

Correct:

Excerpt from a valid request; the real payload must include every allowlisted group and field:

```json
{
  "config": {
    "page_setup": { "top_margin": 2.3, "bottom_margin": 2.3 },
    "heading1": { "font_name": "宋体", "font_size": 14, "bold": true }
  }
}
```

---

## Testing Requirements

<!-- What level of testing is expected -->

(To be filled by the team)

---

## Code Review Checklist

<!-- What reviewers should check -->

(To be filled by the team)
