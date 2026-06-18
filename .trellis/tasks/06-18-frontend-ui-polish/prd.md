# Frontend UI polish with ui-ux-pro-max

## Goal

Improve the visual quality of the md2word frontend using `ui-ux-pro-max` design guidance while preserving the existing Vue 3 + Element Plus + SCSS workbench architecture and all current business behavior.

Confirmed by user.

## What I already know

- The user says the project is mostly complete, but the frontend pages do not look good enough.
- The user explicitly wants to use the `ui-ux-pro-max` skill/plugin as design guidance.
- The user invoked `grill-me`, so requirement discovery should be direct, one question at a time, and should pressure-test vague preferences.
- The frontend stack is Vue 3, Element Plus, SCSS, Vite, Pinia, and Vue Router.
- The project already has a frontend UI system spec under `.trellis/spec/frontend/`.
- The current spec direction is a Stripe/Linear-like internal SaaS workbench: dense, calm, data-first, and task-oriented.
- Current frontend routes include `/login`, `/jobs`, `/jobs/new`, `/jobs/:jobId`, translation QA, settings/configuration, terminology governance, and system/operations pages.
- `frontend/node_modules` exists, so build and smoke validation can run without a dependency install step.
- There is one pre-existing dirty file: `.trellis/spec/frontend/ui-system-guidelines.md`. It was not created by this task and must not be overwritten casually.

## Research References

- [`research/ui-ux-pro-max-design-system.md`](research/ui-ux-pro-max-design-system.md) - `ui-ux-pro-max` output mapped to this project's constraints.

## ui-ux-pro-max Brief

Use the skill as if invoked with:

`/ui-ux-pro-max Polish an existing Vue 3 + Element Plus internal SaaS workbench for document conversion, translation QA, configuration, terminology governance, and operations. Prioritize full-site consistency, data-dense dashboard usability, compact tables, filters, status/evidence panels, action rows, responsive behavior, visible focus states, and a professional internal-system login page. Preserve existing behavior and the current UI stack.`

## Assumptions (temporary)

- This task is primarily presentation/UI polish, not a feature rewrite.
- Existing auth, permissions, route behavior, API calls, upload flow, polling, and guarded action availability must remain unchanged.
- The implementation should reuse existing `--app-*` tokens and shared `app-*` classes rather than importing a new UI kit, remote fonts, or a new palette.

## Open Questions

- None.

## Requirements (evolving)

- Use `ui-ux-pro-max` as guidance, but normalize recommendations to the project UI system.
- Preserve the Vue 3 + Element Plus + SCSS stack.
- Preserve existing frontend behavior and backend interaction contracts.
- Improve the full productized frontend scope with professional SaaS/workbench visual hierarchy, spacing, interaction states, and responsive layout.
- Include main flow pages, settings/configuration pages, system/operations pages, translation QA pages, and terminology governance pages in the consistency pass.
- Use a full-site consistency strategy rather than only improving first-impression entry pages.
- Use a shared-system-first implementation depth: upgrade `main.scss`, `AppLayout.vue`, and shared card/table/filter/status/action styles first, then locally refine pages that remain visibly inconsistent.
- Normalize `/login` toward the protected workbench visual system while keeping light brand/process cues for document conversion.
- Prioritize operational efficiency and cross-page consistency over screenshot-oriented visual impact.
- Make tables, filters, status surfaces, and action rows clearer, tighter, and easier to scan across the full workbench.
- Close the current consistency loop only; do not add theme switching, density settings, layout configuration, or new page/component abstraction layers.
- Include lightweight notes for follow-up page-level refinements discovered during implementation, without expanding the code scope.
- Avoid decorative-only changes that make operational pages less scannable.

## Acceptance Criteria (evolving)

- [ ] Main flow, settings/configuration, system/operations, translation QA, and terminology governance pages share a consistent visual hierarchy aligned with the existing internal SaaS workbench direction.
- [ ] Tables, filters, status indicators, evidence panels, and action areas are easier to scan and use without reducing important information density.
- [ ] Clickable controls and cards provide visible hover and focus feedback without layout shift.
- [ ] Selected pages remain usable at approximately 375px, 768px, 1024px, and 1440px.
- [ ] No route, auth, permission, upload, polling, API payload, or guarded action behavior is intentionally changed.
- [ ] Follow-up visual opportunities, if found, are recorded in task notes or PRD without adding new extensibility code in this pass.
- [ ] `cd frontend && npm run build` passes after implementation.
- [ ] Smoke tests are considered for `/jobs`, `/jobs/new`, and `/jobs/:jobId` if those pages are in scope and the local Playwright browser cache is available.

## Definition of Done

- Requirements are confirmed with the user before implementation.
- Relevant frontend spec files are loaded before coding.
- UI changes are tightly scoped to the confirmed page group.
- Build validation runs successfully, or any blocker is stated precisely.
- Any public behavior or documentation changes are documented.

## Technical Approach

- Strengthen the existing shared UI system before editing individual pages.
- Keep shared visual primitives in `frontend/src/styles/main.scss`: tokens, surface hierarchy, table density, filters, status/evidence panels, focus rings, button/card interaction states, and responsive behavior.
- Refine `frontend/src/layouts/AppLayout.vue` so navigation, header density, breadcrumbs, and mobile behavior match the upgraded system.
- Refine `frontend/src/pages/LoginPage.vue` into a professional internal-system login page: less marketing-like gradient/hero treatment, tighter hierarchy, and a retained PDF-to-DOCX process cue.
- Apply focused local changes only where a page still falls outside the shared workbench direction after global styles are improved.
- Do not replace Element Plus, introduce a new icon library, import remote fonts, or add a second visual token system.
- Do not add theme/density/layout configuration or a new component abstraction layer in this task.
- Record future page-level polish opportunities as lightweight notes only.

## Decision (ADR-lite)

**Context**: Full-site visual consistency is required, but the frontend already has a Vue 3 + Element Plus + SCSS productized workbench and many pages with existing business behavior.

**Decision**: Use a shared-system-first polish strategy with targeted page refinements. Upgrade `main.scss`, `AppLayout.vue`, and reusable workbench surface patterns first; then repair only visibly inconsistent page-level styling.

**Consequences**: This maximizes consistency and keeps risk bounded. It will not produce a dramatic full redesign on every page, but it avoids unnecessary rewrites and preserves behavior contracts.

### Login page direction

**Context**: The current login page is more expressive than the protected workbench and uses a marketing-like visual treatment.

**Decision**: Bring `/login` closer to the workbench design system while preserving light md2word brand/process cues.

**Consequences**: The first screen will feel more professional and consistent with the internal SaaS product. It will lose some decorative impact, intentionally, to avoid visual mismatch with the rest of the app.

### Visual quality priority

**Context**: "Better looking" could mean stronger screenshot impact, better mobile presentation, or more efficient workbench operation.

**Decision**: Prioritize operational efficiency and cross-page consistency. Improve table density, filters, status/evidence areas, action rows, and page hierarchy before decorative polish.

**Consequences**: The result should feel more professional and easier to operate, but it will stay restrained rather than becoming a high-impact marketing-style redesign.

### Future extension boundary

**Context**: A full-site visual polish could easily grow into theme switching, density configuration, or a new design abstraction layer.

**Decision**: Keep this pass to the current visual consistency closure. Do not add new extensibility code; record lightweight follow-up notes for future page-level refinements only.

**Consequences**: The task remains deliverable and lower risk. Future design-system work can still be planned later with clearer evidence from this pass.

## Out of Scope (temporary)

- Replacing Element Plus or adding another UI library.
- Adding remote font imports.
- Changing backend APIs, permissions, auth, route guards, job lifecycle behavior, or upload semantics.
- Theme switching, density switching, layout configuration, or other new UI preference systems.
- New page/component abstraction layers created solely for future flexibility.
- Rebuilding every page from scratch.

## Technical Notes

- Relevant spec: `.trellis/spec/frontend/index.md`.
- Relevant spec: `.trellis/spec/frontend/ui-system-guidelines.md`.
- Main shared style file: `frontend/src/styles/main.scss`.
- Protected shell: `frontend/src/layouts/AppLayout.vue`.
- Key current pages inspected: `frontend/src/pages/LoginPage.vue`, `frontend/src/pages/JobsPage.vue`, `frontend/src/pages/JobCreatePage.vue`.
- Route inventory inspected: `frontend/src/router/index.ts`.
- Current package scripts include `npm run build`, `npm run test:unit`, and `npm run test:smoke`.
