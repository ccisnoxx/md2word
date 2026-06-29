# Internal portal core workflow hardening

## Goal

验证并收口内部门户的 operator/admin 核心工作流，使登录、任务创建、任务详情、QA、下载、配置、验收和运维页面形成可用闭环。

## Evidence

- `docs/runbooks/internal-portal.md` defines the internal portal roles, route map, and acceptance checklist.
- `frontend/src/router/index.ts` implements protected routes and role/permission guards.
- `frontend/src/navigation/appShell.ts` defines processing, quality, configuration, and system navigation groups.
- Frontend unit and Playwright smoke specs already cover portions of auth, core flow, acceptance center, operations cockpit, incident triage, and table preferences.

## Requirements

- R1. Validate the portal as an internal operator/admin tool, not an external customer portal.
- R2. Cover role-based access, route visibility, and forbidden states.
- R3. Cover job create/list/detail/download and translation QA paths.
- R4. Cover admin-only acceptance, users, audit, file retention, configuration, and ops/status paths.
- R5. Record missing empty/error/loading/permission states as fixable findings rather than hiding them with fallbacks.

## Acceptance Criteria

- [ ] Operator can log in, create a job, view job list/detail, download output when available, and enter translation QA where applicable.
- [ ] Operator cannot access admin-only routes or actions, and receives a clear forbidden or navigation state.
- [ ] Admin can access configuration, users, audit, file retention, acceptance center, system status, and ops dashboard routes.
- [ ] Core pages show usable loading, empty, error, and permission states without overlapping or misleading UI.
- [ ] Smoke/mock or staging evidence records the tested accounts, routes, actions, and remaining blockers.

## Out Of Scope

- Building a marketing site, external SaaS portal, billing, SSO, or online Word editor.
- Redesigning the entire visual system.
- Implementing backend product features not needed to close the portal workflow evidence.
