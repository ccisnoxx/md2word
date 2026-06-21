# Next-Stage Product Deepening Acceptance Audit

## Scope

This audit covers the first implementation slice for `06-21-next-stage-product-deepening`.

The slice intentionally covers M0/M1 launch closure and Acceptance Center MVP work only:

- Managed internal user launch-loop evidence and UX hardening.
- Auth and forbidden-route UX hardening.
- Protected long-dialog viewport hardening for the touched job action dialogs.
- Acceptance Center P0/P1/P2 evidence review MVP.
- OpenAPI, API docs, internal portal runbook, release checks, frontend types, wrappers, and smoke mocks.

It does not claim to finish later P2/P3 product ideas such as external SaaS, team assignment, realtime collaboration, broader batch productivity, automatic acceptance evidence import, or terminology-release-as-default resolver wiring.

## Requirement Evidence

| Requirement | Status | Evidence |
| --- | --- | --- |
| R1 User Management Launch Closure | Pass | `scripts/ops/check_release.py` includes `tests.test_internal_user_management`; `docs/api/auth.md`, `docs/api/users.md`, `docs/runbooks/internal-portal.md`, and OpenAPI describe managed users and bootstrap behavior; `frontend/tests/smoke/user-auth.spec.ts` covers visible auth/user UX. |
| R2 UX Hardening For Auth And Admin Flows | Pass | `frontend/tests/smoke/user-auth.spec.ts` verifies password-change success notice, dangerous user disable confirmation, cancel-without-PATCH, and forbidden return to default accessible route. `frontend/src/pages/JobDetailPage.vue` now teleports retry/clone dialogs to body and owns scroll containers. |
| R3 API And Documentation Contract Alignment | Pass | `docs/api/openapi.json` is current; `docs/api/manifest.yaml`, `docs/api/acceptance.md`, and `docs/runbooks/internal-portal.md` were updated; `scripts/ops/check_release.py` checks OpenAPI, frontend wrapper/type needles, Acceptance Center contracts, and user-auth smoke needles. |
| R4 Acceptance Center MVP | Pass | `app/domains/acceptance/*` exposes list/detail/latest-summary/review contracts; review writes audit events; frontend consumes `latest-summary`; smoke covers review flow and responsive overflow; defaults reflect current P0 signoff and explicit P1/P2 blockers. |
| R5 Frontend Implementation Boundaries | Pass | Acceptance work remains in `AcceptanceCenterPage.vue` and `frontend/src/api/acceptance.ts`; Jobs long-dialog fix stays in `JobDetailPage.vue`; no Cockpit aggregate endpoint or global Pinia filter state was added. |

## Acceptance Criteria Evidence

| Acceptance criterion | Evidence |
| --- | --- |
| User-management tests are part of default release check path. | `scripts/ops/check_release.py` default targets include `tests.test_internal_user_management`; latest release check passed. |
| Internal portal and API docs describe managed users, bootstrap behavior, admin operations, and rollback/lockout precautions. | Existing `docs/api/auth.md`, `docs/api/users.md`, and updated `docs/runbooks/internal-portal.md`; release check validates core OpenAPI and frontend contract fields. |
| User-management dangerous actions and auth state changes have clear Chinese feedback. | `frontend/src/pages/UserManagementPage.vue` already shows confirmation/error feedback; `frontend/tests/smoke/user-auth.spec.ts` verifies disable confirmation and password changed login notice. |
| Forbidden users can return to a route they are allowed to access. | `frontend/src/pages/ForbiddenPage.vue` uses `getDefaultProtectedRoute`; `frontend/tests/smoke/user-auth.spec.ts` verifies operator returns to `/cockpit`. |
| Acceptance Center backend APIs exist, are admin-protected where writes occur, and never expose secrets. | `app/domains/acceptance/router.py` uses `require_admin_user`; response schemas contain compact metadata only; targeted API tests cover unauthorized/forbidden paths. |
| Acceptance review decisions write audit events. | `tests/test_acceptance_center_api.py` asserts `acceptance_run.review` audit event details. |
| Acceptance Center frontend page shows gate summaries, blockers, reports, and review controls. | `frontend/src/pages/AcceptanceCenterPage.vue` uses latest summary and run details; `frontend/tests/smoke/acceptance-center.spec.ts` exercises rendered summary and review flow. |
| P0/P1/P2 evidence summaries can be reviewed without changing conversion, QA, terminology, or ops workflow behavior. | Acceptance service stores compact metadata and review fields only; docs state Acceptance Center is an evidence index, not an executor. |
| OpenAPI snapshot and manifest/docs are updated for new or changed public contracts. | `docs/api/openapi.json`, `docs/api/manifest.yaml`, `docs/api/acceptance.md`, and `docs/runbooks/internal-portal.md` updated; release check says OpenAPI current. |
| Targeted backend tests, frontend unit/build checks, and relevant smoke/visual checks pass or skipped validation is justified. | See validation log below. |

## Validation Log

Observed passing checks during this task:

- `env PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests.test_acceptance_center_api` -> 3 tests passed.
- `env PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/ops/check_release.py` -> passed; OpenAPI current; frontend contract ok; frontend smoke mock needles ok; 146 targeted tests passed.
- `npm --prefix frontend run test:unit` -> 20 files / 79 tests passed.
- `npm --prefix frontend run build` -> passed; existing Rollup PURE annotation and chunk-size warnings remain.
- `npm --prefix frontend run test:smoke -- acceptance-center.spec.ts --reporter=line --output=/private/tmp/md2word-acceptance-smoke-results` -> 4 tests passed with escalated Chrome launch.
- `npm --prefix frontend run test:smoke -- user-auth.spec.ts --reporter=line --output=/private/tmp/md2word-user-auth-smoke-results` -> 3 tests passed with escalated Chrome launch.
- `git diff --check` -> passed.

## Residual Risks

- The current slice does not automatically import fresh P0/P1/P2 run reports into Acceptance Center; starter summaries must still be replaced by latest script reports or manual summaries for release evidence.
- Local Playwright smoke requires escalated Chrome launch in this environment; outputs were written to `/private/tmp` to avoid repository test-result churn.
- Existing frontend build warnings from Rollup PURE annotations and large bundle size remain unchanged.
- File backend remains a local/single-process metadata backend and should not be treated as production account truth.
- The larger product deepening plan still has later-stage ideas outside this slice, including broader productivity and evidence automation work.
