# Internal portal core workflow hardening design

## Boundary

This task hardens the existing internal Vue portal and its evidence, not the backend product contract. Backend role checks, document-job action availability, and Acceptance Center semantics remain authoritative. Frontend changes should only align UI behavior, mocks, and tests with those contracts.

## Current Architecture

- `frontend/src/router/index.ts` owns route-level auth, role, and permission guards.
- `frontend/src/navigation/appShell.ts` owns sidebar IA, default protected route selection, breadcrumbs, and page ownership.
- `frontend/src/stores/auth.ts` normalizes current-user roles and permissions, including legacy role-only responses.
- `frontend/src/components/JobActions.vue` and `frontend/src/components/JobTable.vue` render document-job lifecycle actions through helpers in `frontend/src/utils/format.ts`.
- `frontend/tests/smoke/core-flow.spec.ts` exercises the operator/admin browser workflows with mocked API responses.

## Contracts

- Operator routes: `/cockpit`, `/jobs`, `/jobs/new`, `/jobs/:jobId`, `/translation-qa`, `/jobs/:jobId/translation-qa`, and operator-visible proposal flows.
- Admin routes: `/settings/**`, `/system-status/**`, `/system-status/users`, `/system-status/acceptance`, `/system-status/file-retention`, and `/system-status/ops-dashboard`.
- Document-job lifecycle action rendering must follow `available_actions`. Delete has an additional visibility rule: when the backend returns disabled reason `只有 admin 可以删除文档任务。`, the delete action is hidden for operator-facing pages.
- Smoke tests should mock the same action availability that the backend exposes for operator/admin accounts. A mock that contradicts the backend contract is treated as misleading evidence.

## First Implementation Pass

The first pass will not add new routes or new backend features. It will:

- Update core-flow smoke fixtures so operator jobs carry the admin-only delete disabled reason.
- Add browser assertions that operator list/detail workflows do not expose the delete action while preserving allowed actions such as download, clone, archive, and QA review.
- Keep existing admin smoke paths for configuration, system status, ops, and file retention intact.
- Run targeted unit and smoke validation for the touched helpers and workflows.

## Rollback

All changes are test and frontend-contract scoped. If the smoke update exposes a real UI regression, rollback is to restore the prior fixture/assertion patch and record the blocker in this task before making product behavior changes.
