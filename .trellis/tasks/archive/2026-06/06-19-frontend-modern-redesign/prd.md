# Modern frontend redesign

## Goal

Refresh the md2word frontend into a modern internal document-conversion workbench with polished animation and first-class dark mode, while preserving existing backend contracts, routes, auth/permission behavior, and core document job workflows.

## What I Already Know

- User requested using `.codex/skills/ui-ux-pro-max` to redo the md2word frontend page with modern feel, animation, and dark mode.
- Frontend lives in `frontend/` and uses Vue 3, Vite, TypeScript, Element Plus, Pinia, and Vue Router.
- Existing routes include login, jobs, job create/detail, translation QA, settings/config, term proposals, and system status.
- Current global styling already has app tokens, glass-like panels, and a theme toggle, but needs a more cohesive redesign and stronger dark-mode coverage.
- The product is an authenticated internal operations workbench, not a public marketing site.

## Assumptions

- The MVP should target the core surfaces users see most: login, protected shell/navigation, job list dashboard, job creation/upload flow, and shared visual tokens.
- Public behavior and API payloads should not change.
- No new dependency should be added unless the existing stack cannot support the requested UI quality.

## Open Questions

- None.

## Requirements

- Apply a cohesive modern design system across the frontend.
- Support light, dark, and system theme modes through the existing theme utility.
- Add tasteful, accessible animation for page entry, hover/focus feedback, loading states, and major workflow elements.
- Keep the authenticated workbench dense and scannable for repeated operator use.
- Preserve existing routing, permission checks, API calls, forms, validations, and job actions.
- Respect `prefers-reduced-motion`.
- Keep mobile/tablet/desktop responsive layouts usable.
- Redesign every existing frontend page in this task, including settings, terminology, QA, system status, audit, retention, templates, and detail pages.

## Acceptance Criteria

- [x] Login page visually matches the redesigned system and works in light/dark modes.
- [x] Protected app layout has modern navigation, theme toggle, and responsive behavior.
- [x] Job list dashboard and core upload/create flow use the refreshed tokens, components, and animations.
- [x] Secondary settings/status/QA/terminology/admin pages all inherit or receive the redesigned page treatment.
- [x] No user-facing workflow regression in auth, navigation, job listing, filtering, upload, or job actions.
- [x] Build/typecheck passes for `frontend`.
- [x] At least one smoke or targeted frontend check is run, or skipped with a clear reason.

## Definition of Done

- Frontend code updated with scoped, behavior-preserving changes.
- Relevant comments/docs updated only where public contracts or non-obvious logic changes.
- `npm run build` or equivalent frontend validation run.
- Residual risks called out.

## Research References

- [`research/ui-design-system.md`](research/ui-design-system.md) - UI Pro Max findings and selected design direction.

## Technical Approach

- Refresh global tokens in `frontend/src/styles/main.scss`, including explicit dark theme tokens.
- Rework `frontend/src/layouts/AppLayout.vue` for a modern command-center shell without changing route/auth logic.
- Rework `frontend/src/pages/LoginPage.vue` as the unauthenticated brand entry.
- Rework core job workflow surfaces (`JobsPage.vue`, `JobCreatePage.vue`, `PdfUploadPanel.vue`, and closely related shared components if needed).
- Rework all secondary pages enough that the full app reads as one coherent modern interface, using shared tokens and local scoped styles where necessary.
- Use existing Element Plus icons rather than adding a new icon dependency.
- Prefer CSS transitions/keyframes and Vue state already present over new animation libraries.

## Out of Scope

- Backend/API changes.
- Route, permission, or auth semantics changes.
- Adding a charting, animation, or component library.

## Technical Notes

- Relevant files inspected: `frontend/package.json`, `frontend/src/App.vue`, `frontend/src/router/index.ts`, `frontend/src/styles/main.scss`, `frontend/src/layouts/AppLayout.vue`, `frontend/src/pages/LoginPage.vue`, `frontend/src/pages/JobsPage.vue`.
- Existing repository has many uncommitted changes unrelated to this task; implementation must avoid reverting or committing unrelated files.
- Validation run:
  - `npm run build` passed.
  - `npm run test:unit -- src/utils/theme.test.ts` passed.
  - `curl -I http://127.0.0.1:3000/login` returned `200 OK` from the local Vite server.
  - Playwright screenshot verification was attempted but blocked because the local Playwright Chromium executable is missing; `npx playwright install chromium` was approved and started but did not complete before being cancelled after a long no-output wait.
