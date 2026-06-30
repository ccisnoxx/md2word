# Internal portal core workflow hardening

## Goal

验证并收口内部门户的 operator/admin 核心工作流，使登录、任务创建、任务详情、QA、下载、配置、验收和运维页面形成可用闭环。

## Evidence

- `docs/runbooks/internal-portal.md` defines the internal portal roles, route map, and acceptance checklist.
- `frontend/src/router/index.ts` implements protected routes and role/permission guards.
- `frontend/src/navigation/appShell.ts` defines processing, quality, configuration, and system navigation groups.
- Frontend unit and Playwright smoke specs already cover portions of auth, core flow, acceptance center, operations cockpit, incident triage, and table preferences.

## Confirmed Facts

- The portal is an internal operator/admin tool; it is not an external customer portal, SaaS console, billing surface, SSO project, or online Word editor.
- Route access is enforced by route `roles` / `permissions` metadata, and sidebar visibility is derived from the same access context.
- Backend document-job action availability is the source of truth for lifecycle actions; frontend code must not invent alternate retry/cancel/archive/delete rules.
- Task-level delete is admin-only by backend contract. Operator-facing workbench evidence must prove the delete affordance is hidden or unavailable when the server returns the admin-only disabled reason.
- Existing smoke coverage spans core flow, auth/forbidden, Acceptance Center, operations cockpit, incident triage, and table preferences; this task should extend those checks before adding new product behavior.

## Requirements

- R1. Validate the portal as an internal operator/admin tool, not an external customer portal.
- R2. Cover role-based access, route visibility, and forbidden states.
- R3. Cover job create/list/detail/download and translation QA paths.
- R4. Cover admin-only acceptance, users, audit, file retention, configuration, and ops/status paths.
- R5. Record missing empty/error/loading/permission states as fixable findings rather than hiding them with fallbacks.
- R6. Keep the first implementation pass evidence-focused: harden the role/action contract and workflow smoke tests before changing product behavior.

## Acceptance Criteria

- [x] Operator can log in, create a job, view job list/detail, download output when available, and enter translation QA where applicable.
- [x] Operator cannot access admin-only routes or actions, and receives a clear forbidden or navigation state.
- [x] Admin can access configuration, users, audit, file retention, acceptance center, system status, and ops dashboard routes.
- [x] Core pages show usable loading, empty, error, and permission states without overlapping or misleading UI.
- [x] Smoke/mock or staging evidence records the tested accounts, routes, actions, and remaining blockers.
- [x] Operator workbench and detail views do not expose task delete when backend action availability says delete is admin-only.

## Validation Evidence 2026-06-30

- `npm run test:unit -- src/utils/format.test.ts src/navigation/appShell.test.ts src/stores/auth.test.ts` passed: 3 files, 17 tests.
- `npm run build` passed: `vue-tsc --noEmit && vite build`.
- `npm run test:smoke -- core-flow.spec.ts user-auth.spec.ts acceptance-center.spec.ts` passed: 22/22.
- Tested accounts and routes: operator login, jobs list/detail/create/download, translation QA queue/drawer/detail panel, admin forbidden handling for operator routes, admin Word style configuration, users, Acceptance Center, system status, audit logs, ops dashboard, and file retention.
- Remaining blockers: none for this task. Existing release-level warnings remain tracked in Acceptance Center/P1/P2 evidence and are not internal portal blockers.

## Out Of Scope

- Building a marketing site, external SaaS portal, billing, SSO, or online Word editor.
- Redesigning the entire visual system.
- Implementing backend product features not needed to close the portal workflow evidence.
