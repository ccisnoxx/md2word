# Frontend information architecture implementation plan

## Gate

Do not run `task.py start` or edit frontend code until this plan is reviewed.

## Steps

1. Update route metadata and guard.
   - File: `frontend/src/router/index.ts`
   - Add `SystemStatusPage` route.
   - Add `meta.roles = ["admin"]` to settings routes and `/system-status`.
   - Extend `beforeEach` to redirect unauthorized role access to `/jobs` after user loading.

2. Update main navigation.
   - File: `frontend/src/layouts/AppLayout.vue`
   - Replace static `navItems` with computed role-aware nav items.
   - Show Admin entries only for `auth.user?.role === "admin"`.
   - Keep responsive header behavior and existing visual style.

3. Add lightweight system status entry page.
   - File: `frontend/src/pages/SystemStatusPage.vue`
   - Render an Admin-only page shell that makes clear this is a read-only system status entry.
   - Do not fetch health APIs in this task.

4. Verify.
   - Run `cd frontend && npm run build`.
   - Run `python3 ./.trellis/scripts/task.py validate 06-03-frontend-information-architecture`.

## Review Checks

- Confirm Operator nav does not include Admin-only entries.
- Confirm Admin nav includes all Phase 1 information architecture entries.
- Confirm direct Operator access to Admin-only URLs is guarded.
- Confirm no backend files or pdf-mineru workflow files changed.

## Rollback Point

If the route guard causes login redirects or public-route behavior to regress, revert only `frontend/src/router/index.ts` and keep navigation/page changes separate for review.

## Verification Results

- `cd frontend && npm run build` passed.
- `python3 ./.trellis/scripts/task.py validate 06-03-frontend-information-architecture` passed.
- Playwright local smoke passed:
  - Operator mock visiting `/settings` redirected to `/jobs` and saw only `任务工作台` / `术语建议`.
  - Admin mock visiting `/system-status` stayed on `/system-status` and saw `任务工作台` / `配置中心` / `提案审核` / `系统状态`.
