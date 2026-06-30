# Internal portal core workflow hardening implementation plan

## Checklist

- [x] Align `frontend/tests/smoke/core-flow.spec.ts` operator document-job fixtures with backend admin-only delete action availability.
- [x] Add operator list-view assertion that the row action dropdown does not show `删除` when delete is admin-only.
- [x] Add operator detail-view assertion that shared job actions do not show the delete button when delete is admin-only.
- [x] If assertions fail because UI behavior is wrong, fix the smallest frontend helper/component path instead of adding a parallel permission check.
- [x] Update task evidence after validation with commands run and any remaining blockers.

## Validation

Run the smallest relevant checks first:

```bash
cd frontend
npm run test:unit -- src/utils/format.test.ts src/navigation/appShell.test.ts src/stores/auth.test.ts
npm run test:smoke -- core-flow.spec.ts user-auth.spec.ts
```

If the smoke set is too slow or browser dependencies fail locally, run the unit checks and record the exact Playwright blocker.

## Implementation Notes 2026-06-30

- `frontend/tests/smoke/core-flow.spec.ts` now treats backend `available_actions.delete` as admin-only for operator fixtures and asserts both list and detail views do not expose `删除`.
- The same smoke coverage now includes the admin audit log route, alongside system status, ops dashboard, file retention, configuration, users, auth, and Acceptance Center evidence.
- `frontend/src/components/PdfUploadPanel.vue` shows the first disabled translation-mode readiness reason even when another mode remains selected, preserving the existing config/readiness source of truth.
- `frontend/src/pages/JobsPage.vue` aligns tablet page padding with the app shell so the operations redesign smoke screenshots do not produce body overflow at 768px.

## Validation Evidence 2026-06-30

```bash
cd frontend
npm run test:unit -- src/utils/format.test.ts src/navigation/appShell.test.ts src/stores/auth.test.ts
npm run build
npm run test:smoke -- core-flow.spec.ts user-auth.spec.ts acceptance-center.spec.ts
```

- Unit tests passed: 3 files, 17 tests.
- Build passed: `vue-tsc --noEmit && vite build`.
- Relevant smoke passed: 22/22.
- No new fallback permission source, backend behavior, deployment behavior, external service call, or destructive operation was introduced.

## Review Gate

Before archive, confirm:

- operator/admin route and navigation expectations still match `docs/runbooks/internal-portal.md`;
- no new fallback permission source was introduced;
- tests prove the role/action contract instead of only checking static text;
- no backend, deployment, or external service behavior changed.
