# Frontend information architecture design

## Scope

This task is a narrow frontend information architecture change.

In scope:
- Protected workbench layout navigation.
- Route metadata for Admin-only pages.
- Frontend route guard for direct Admin-only URL access.
- A lightweight Admin-only system status entry page so the navigation has a valid destination.

Out of scope:
- Backend API changes.
- Full system status dashboard data binding.
- Complete term rule CRUD workbench.
- File deletion or file management.
- Any pdf-mineru parse / translation / DOCX generation workflow execution.

## Current State

`frontend/src/layouts/AppLayout.vue` renders a compact header with only one navigation item: `/jobs`.

`frontend/src/router/index.ts` already exposes:
- `/jobs`
- `/jobs/:jobId`
- `/settings`
- `/settings/templates`
- `/settings/term-rule-sets`
- `/settings/translation-profiles`
- `/settings/templates/:templateId`
- `/term-proposals`

The router only checks authentication. It does not enforce role metadata. `RoleGate.vue` hides controls inside pages, but does not protect direct navigation.

There is no `/system-status` route yet. Health APIs exist, but the full status page belongs to `admin-system-status`.

## Role Model

Use the existing `auth.user?.role` string.

Navigation:
- All authenticated users: `/jobs`.
- Operator/Admin: `/term-proposals`.
- Admin only: `/settings` and `/system-status`.

Labels:
- `/term-proposals` label should be role-aware:
  - Admin: `提案审核`
  - non-admin: `术语建议`
- Keep `/settings` as `配置中心`.
- Keep `/system-status` as `系统状态`.

Route protection:
- Add route `meta.roles = ["admin"]` to Admin-only routes.
- In `beforeEach`, after loading the current user, redirect unauthorized role access to `/jobs`.
- Keep public `/login` behavior unchanged.

## Page / API Changes

Frontend page changes:
- Update `AppLayout.vue` to compute role-aware nav items from the auth store.
- Update `router/index.ts` with role metadata and guard logic.
- Add `frontend/src/pages/SystemStatusPage.vue` as a lightweight Admin-only destination.

Backend API changes:
- None.

New API calls:
- None.

Deferred to `admin-system-status`:
- `GET /api/v1/health/ready` binding.
- `GET /api/v1/health/metrics` binding.
- Worker/backend/storage/resource status cards.
- Links to failed/running job filters.

## Compatibility

Existing paths remain stable. Existing page components keep their current contracts. The only behavioral change is that non-admin users can no longer directly open configuration routes from a copied URL.

## Risks

- If an environment has non-standard role strings, route gating will only allow exact `admin`. This matches existing `RoleGate.vue` behavior.
- The system status page is intentionally lightweight in this task, so it must not be treated as the completed ops status dashboard.
