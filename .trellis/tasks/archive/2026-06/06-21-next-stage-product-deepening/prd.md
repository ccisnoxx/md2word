# Execute Next-Stage Product Deepening Plan

## Goal

Execute the agreed next-stage plan for md2word: turn the existing internal PDF-to-Word and translation workbench into a more complete internal technical document delivery quality platform.

The first implementation slice must prioritize the M0 and M1 outcomes from the planning session:

- close the internal user management launch loop;
- harden high-risk UX feedback around user/auth flows and long dialogs;
- keep API/docs/release gates aligned with implemented contracts;
- add an Acceptance Center MVP so admins can review current P0/P1/P2 delivery evidence and record pass/block decisions.

This task intentionally does not attempt to finish every P2/P3 idea from the plan.

## Product Positioning

md2word is an internal technical document delivery quality platform, not a generic PDF converter, SaaS product, or customer portal.

The product serves internal operators, administrators, and quality reviewers who need technical datasheet PDF-to-Word conversion, English-to-Chinese translation QA, terminology/config governance, operational readiness, and auditable acceptance evidence.

## Requirements

### R1. User Management Launch Closure

- Treat managed internal users as the operational account source after bootstrap.
- Keep only `admin` and `operator` roles in scope.
- Keep SSO, MFA, self-registration, custom permission matrices, account lockout, and complex password policies out of this slice.
- Update release checks so user-management regressions are covered by default.
- Update internal portal/API docs so operators do not continue using legacy JSON editing as the normal account-management workflow.
- Preserve last-active-admin protection, token invalidation, safe API responses, and audit behavior.

### R2. UX Hardening For Auth And Admin Flows

- User management create/edit/reset/enable/disable flows must show clear confirmation or persistent error feedback where the action is dangerous or failure-prone.
- Password-change success must be visible on the login page after redirect.
- Forbidden-page return behavior must send users to their default accessible protected route, not always `/jobs`.
- Long dialogs in protected workbench pages must append to body, keep footer actions reachable, and own their scroll container.

### R3. API And Documentation Contract Alignment

- Keep OpenAPI as the primary machine-readable contract.
- Keep `docs/api/manifest.yaml`, relevant API markdown, and internal portal runbook aligned with implemented users/auth/acceptance contracts.
- Do not expose password hashes, tokens, secrets, or full prompt/response text in user, job, or acceptance responses.
- Review `DocumentJobResponse.request_snapshot` before broadening acceptance evidence; expose only safe summaries if acceptance pages need job configuration context.

### R4. Acceptance Center MVP

Add an admin-facing acceptance evidence center that answers:

> Can the current internal delivery version be accepted, what blocks it, and who signed off?

MVP behavior:

- Provide a compact page under the protected internal portal for acceptance evidence.
- Show recent P0 Golden Sample, P1 translation, and P2 online gate runs or manually recorded summaries.
- Show status, environment, report path/URL, blockers, timestamps, reviewer, review status, and review note.
- Allow admin users to record an `approved`, `rejected`, or `needs_changes` review decision.
- Record audit events for acceptance review decisions.
- Provide links or references to existing reports and related operational pages when available.
- Do not store large artifacts, secrets, JWTs, raw customer text, full LLM prompts/responses, or binary files in acceptance metadata.

Recommended backend contract:

- `GET /api/v1/acceptance/runs`
- `GET /api/v1/acceptance/runs/{run_id}`
- `GET /api/v1/acceptance/runs/latest-summary`
- `POST /api/v1/acceptance/runs/{run_id}/review`

Recommended data fields:

- `id`
- `tier`: `P0`, `P1`, `P2`
- `status`: `passed`, `failed`, `unknown`
- `environment`
- `source`
- `report_path_or_url`
- `summary`
- `blockers`
- `warnings`
- `started_at`
- `finished_at`
- `decision`: `approved`, `rejected`, `needs_changes`, or `null`
- `reviewer`
- `review_note`
- `reviewed_at`
- `updated_at`

Recommended latest-summary fields:

- `overall_status`: `accepted`, `blocked`, `incomplete`, or `needs_attention`
- `missing_tiers`
- `blocker_count`
- `warning_count`
- `latest_reviewed_run`
- `tiers`
- `generated_at`

### R5. Frontend Implementation Boundaries

- Keep `/cockpit` as a launch surface, not a BI dashboard or second queue implementation.
- Keep Jobs, QA, Incident, and Acceptance pages as separate ownership surfaces.
- Reuse existing Element Plus, `ApiErrorAlert`, navigation, auth store, compact workbench styles, and route permission patterns.
- Keep URL query as the source of truth for queue/drawer deep links; do not move Jobs/QA/Incident filters into global Pinia.

## Acceptance Criteria

- [x] User-management tests are part of the default release check path.
- [x] Internal portal and API docs describe managed users, bootstrap behavior, admin operations, and rollback/lockout precautions.
- [x] User-management dangerous actions and auth state changes have clear Chinese feedback.
- [x] Forbidden users can return to a route they are actually allowed to access.
- [x] Acceptance Center backend APIs exist, are admin-protected where writes occur, and never expose secrets.
- [x] Acceptance review decisions write audit events.
- [x] Acceptance Center frontend page shows gate summaries, blockers, reports, and review controls.
- [x] P0/P1/P2 evidence summaries can be reviewed without changing conversion, QA, terminology, or ops workflow behavior.
- [x] OpenAPI snapshot and manifest/docs are updated for new or changed public contracts.
- [x] Targeted backend tests, frontend unit/build checks, and relevant smoke/visual checks pass or any skipped validation is explicitly justified.

## Out Of Scope

- Generic PDF expansion beyond technical datasheets.
- External SaaS, multi-tenant billing, customer portal, online Word editing.
- SSO/OIDC/SAML/LDAP, MFA, password history, lockout, forced password change, full IAM.
- Team assignment, team shared views, drag/drop dashboard customization.
- New Incident persistence table or Cockpit aggregate endpoint unless proven necessary.
- Automatically using terminology governance releases as the default document-job asset resolver in this slice.

## Technical Approach

- First close M0 hardening and release gate gaps before adding Acceptance Center.
- Use existing backend patterns: domain router/service/schemas/models/repository protocol plus file/sqlite/mysql adapters where metadata must persist.
- Use existing frontend patterns: static route + navigation entry + Element Plus workbench page + API wrapper + TypeScript contracts.
- Keep Acceptance Center metadata small and auditable; report content remains in existing files/pages/scripts.
- Use `AuditService` for acceptance review actions.

## Verification Plan

Backend:

- `python -m unittest tests.test_internal_user_management`
- `python -m unittest tests.test_saved_views tests.test_saved_views_api`
- `python -m unittest tests.test_terminology_releases`
- relevant `tests.test_fastapi_jobs_backend` incident/document-job tests
- `python -m unittest tests.test_openapi_export`
- `python scripts/ops/check_release.py`

Frontend:

- `cd frontend && npm run build`
- `cd frontend && npm run test:unit`
- relevant Playwright smoke checks for cockpit, jobs, QA drawer, incident drawer, user management, and Acceptance Center where practical.
- Visual/manual checks at 1440px, 768px, and 375px for changed protected pages and dialogs.

## Risks And Decisions

Default decisions:

- Prioritize acceptance and launch closure over batch productivity.
- Keep Cockpit as frontend-composed multi-source UI for now.
- Keep role model limited to `admin` and `operator`.
- Keep department scope as a stored field only; do not add department permission semantics now.
- Keep OpenAPI as the contract source and update manifest/runbook alongside it.

Risks:

- Existing active Trellis tasks may reflect work already committed but not archived.
- API docs and runbooks currently lag behind managed-user implementation.
- Acceptance report sources may be partly script/file based; MVP must not depend on unstable temporary paths as the only long-term truth.
- File backend remains local/single-process oriented and should not be treated as production account truth.
