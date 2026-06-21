# Execute Next-Stage Product Plan

## Goal

Execute the next-stage product plan for md2word by moving the product from
"many implemented workbench capabilities" to a coherent internal delivery
quality platform.

The first execution slice must prioritize P0 launch closure:

- make the PDF-to-Word delivery loop easier to operate and verify;
- close currently active user-management and long-dialog launch risks;
- keep Acceptance Center evidence honest and release-ready;
- harden high-risk UX paths without expanding product scope.

This task does not attempt to finish every P1/P2 idea from the product plan.
Future slices can continue from this PRD after the P0 items are verified.

## Product Positioning

md2word is an internal technical document delivery quality platform for
technical datasheet / electronic-document PDF-to-Word conversion, translation
QA, terminology/config governance, operations readiness, and acceptance
evidence.

It is not a generic PDF converter, external SaaS product, customer portal,
online Word editor, or full IAM platform.

## Target Users And Core Scenarios

- `operator`: upload PDFs, create jobs, track progress, handle failed or stale
  jobs, download DOCX output, and submit terminology suggestions.
- `QA/reviewer`: process `en2zh_pdf_to_word` QA items, inspect evidence, record
  review status, and identify terminology/config issues.
- `admin`: manage templates, page styles, terminology and translation assets,
  internal users, audit logs, and acceptance evidence.
- `ops/admin`: inspect readiness, storage/capacity, retention, gated recovery
  actions, and release evidence.

## Requirements

### R1. P0 Delivery Loop Closure

- Keep `Files + Document Jobs` as the public P0 workflow.
- Preserve the existing upload -> create -> status/events/files -> download
  path and the existing retry/clone/cancel/archive/delete semantics.
- Do not add a second job state source, persistent incident table, or cockpit
  aggregate endpoint unless benchmarking proves the current API composition is
  not sufficient.
- Ensure job-facing release evidence remains based on current OpenAPI, API docs,
  and release checks rather than stale historical docs.

### R2. User Management Launch Closure

- Treat managed internal users as the runtime account source after bootstrap.
- Keep only `admin` and `operator` roles in this slice.
- Keep SSO, MFA, self-registration, custom permission matrices, forced password
  changes, and user deletion out of scope.
- Preserve last-active-admin protection, token invalidation, safe user
  responses, and audit behavior.
- Verify admin-only navigation, operator forbidden behavior, self password
  change, reset password, enable/disable, and empty query parameter handling.

### R3. Long Dialog And High-Risk UX Hardening

- Workbench dialogs opened from protected pages must append to `body`, keep
  header/footer actions reachable, and own their body scroll container.
- The Term Rule Set draft-rule create/edit dialog must satisfy that contract on
  desktop, tablet, and mobile widths.
- High-risk operations must make side effects clear near the action. Where a
  backend preview/reason/confirmation/audit contract exists, the frontend must
  expose it instead of reducing the action to a simple toast.
- Blocking API errors must use the shared structured error UI where practical.

### R4. Acceptance Evidence Honesty

- Acceptance Center is an evidence index and review surface, not an execution
  engine and not a second source of release truth.
- Starter summaries may guide admins but must not be treated as fresh release
  evidence for P1/P2 or future P0 releases.
- `latest-summary` must remain a derived view over compact acceptance run
  metadata.
- Review decisions must update reviewer metadata only; they must not change run
  `status`, `blockers`, or `warnings`.
- Acceptance metadata must never store PDF/DOCX binaries, JWTs, secrets, raw
  customer text, full prompts, full provider responses, local object paths, or
  presigned URLs.

### R5. API, Docs, And Release Gate Alignment

- Keep OpenAPI as the machine-readable public contract.
- Keep `docs/api/manifest.yaml`, relevant `docs/api/*.md`, and internal runbooks
  aligned with implemented auth/users/document-jobs/acceptance behavior.
- Do not expose password hashes, bearer tokens, secrets, full prompts, or full
  provider responses in public responses or audit details.
- When API contracts change, update backend schema/tests, API docs, frontend
  types/wrappers, and release checks together.

## P0 Implementation Plan

1. Verify current state against this PRD:
   - active user-management task;
   - active draft-rule dialog task;
   - Acceptance Center defaults and docs;
   - release-check and OpenAPI coverage.
2. Close low-risk gaps first:
   - documentation or contract mismatches that could mislead operators/admins;
   - frontend query/feedback/layout issues with targeted scope;
   - acceptance evidence wording that implies stale starter data is fresh.
3. Run targeted checks:
   - backend tests for affected domain/API contracts;
   - `frontend` build and unit/smoke checks for affected pages;
   - release check when API/docs/OpenAPI behavior changes.
4. Record residual P1/P2 follow-up items without implementing them in this
   slice.

## Acceptance Criteria

- [x] A current Trellis PRD exists for executing the product plan.
- [x] Implement/check context references the backend, frontend, and cross-layer
      project specs needed for follow-up implementation.
- [x] User-management launch behavior is verified or remaining gaps are captured
      with concrete file/test targets.
- [x] Term Rule Set draft-rule dialog behavior is verified or fixed with no API
      behavior changes.
- [x] Acceptance Center wording and tests make clear that starter summaries are
      not fresh release evidence.
- [x] API docs, OpenAPI, and release checks are consistent with any contract
      changes made in this task.
- [x] Targeted backend/frontend checks are run, or skipped checks are explicitly
      justified.

## Execution Notes

- 2026-06-21: clarified Acceptance Center starter-summary semantics in backend
  defaults, frontend warning copy, API docs, and internal runbook. P0 starter
  data now presents as historical guidance that must be replaced before the
  next release, not as fresh release evidence.
- 2026-06-21: verified user-management launch behavior with
  `tests.test_internal_user_management`; no implementation change was needed in
  this slice.
- 2026-06-21: reran Playwright smoke outside the command sandbox after Chrome
  launch failed inside the sandbox; `acceptance-center.spec.ts` and
  `term-rule-set-dialog.spec.ts` passed in real Chrome.
- 2026-06-21: added `frontend/src/pages/TermRuleSetPage.test.ts` as a static
  contract guard for the draft-rule dialog mounting and scroll behavior. This
  protects the page contract alongside the desktop/tablet/mobile smoke check.
- 2026-06-21: fixed teleported dialog styling for draft-rule, job-action, and
  user-management dialogs by applying Element Plus internal selectors through
  `:global(...)`; scoped `:deep(...)` did not affect the body-mounted dialog
  internals in browser smoke.
- 2026-06-21: updated `.trellis/spec/frontend/layout-guidelines.md` with the
  body-mounted dialog `:global(...)` convention and required computed-style
  smoke assertions.

## Out Of Scope

- Generic PDF expansion, external SaaS, multi-tenant billing, customer portal,
  and online Word editing.
- SSO/OIDC/SAML/LDAP, MFA, password history, account lockout, self-registration,
  deletion, or full IAM.
- Team assignment, shared team views, BI dashboards, WebSocket/SSE realtime
  updates, or cockpit backend aggregation by default.
- Real S3 deletion, real provider cancellation, autonomous cleanup scheduler
  execution, or default real external notification delivery.
- Automatically making terminology governance releases the Document Job default
  asset resolver without a separate design decision.

## Verification Plan

Backend:

- `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_internal_user_management`
- `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_acceptance_center_api`
- `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_openapi_export`
- `/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/check_release.py`

Frontend:

- `cd frontend && npm run build`
- `cd frontend && npm run test:unit`
- Relevant smoke checks for user auth, acceptance center, operations cockpit,
  incident triage, and the term-rule dialog if the local browser environment is
  available.

Visual/layout verification:

- Verify affected protected pages at 1440px, 768px, and 375px.
- Confirm no uncontrolled document/body horizontal overflow.
- Confirm long dialog footer actions remain reachable.

## Defaults And Decisions

- Keep route paths stable in this slice.
- Keep Cockpit frontend-composed unless performance evidence proves otherwise.
- Keep `department_id` as a stored user field only; do not add department
  permission semantics.
- Treat MySQL + Celery/Redis + single worker as the production operations
  baseline; file/sqlite remain local or low-concurrency metadata backends unless
  existing code already supports a feature there.
- Keep real destructive/external operations gated until a dedicated task
  designs, implements, and verifies the safety contract.
