# Frontend Experience Hardening And Visual QA

## Goal

Harden the high-frequency operations frontend before continuing with any new feature work. This tenth round should verify and polish the experience created across the previous operations rounds: dense Jobs workbench, Translation QA queue and drawer, app shell/sidebar, Incident triage, saved views, personal cockpit, command palette, table preferences, and diagnostic detail surfaces.

This is a consolidation round. The goal is not to add more workflow surface area. The goal is to make the existing operator paths visually consistent, Chinese-first, responsive, keyboard-usable, and ready for repeated daily use.

## Product Positioning

The frontend is a high-frequency operations workbench for Chinese-speaking operators.

Design priorities:

- density and scan efficiency
- low visual noise
- Chinese visible copy
- predictable list, filter, batch, QA, diagnostic, and drawer behavior
- stable responsive layout
- clear loading, empty, and error states
- evidence from browser or Playwright checks

The interface should feel like a focused operations console, not a marketing SaaS page, tutorial, or decorative dashboard.

## Current Context

- The project uses Vue 3 and Element Plus under `frontend/`.
- `OperationsCockpitPage.vue` is the protected landing surface and default operations launch page.
- Jobs, Translation QA, and Incident pages now have dense workbench patterns, saved views, command palette integration, table preferences, and diagnostic surfaces.
- `TranslationQaReviewPanel.vue`, `IncidentTriagePage.vue`, and `JobDetailPage.vue` now carry important diagnostic and evidence-reading workflows.
- Existing smoke tests already cover core operations flows, cockpit behavior, incident triage, and table preferences.
- `.trellis/spec/frontend/layout-guidelines.md` defines the protected shell, workbench density, page-level drawers, mobile table handling, and required layout verification rules.

## Problems And Recommended Choices

| Problem | Options | Recommended Choice |
|---|---|---|
| Tenth-round direction | 1. Add another feature; 2. harden release-readiness and visual QA; 3. redesign from scratch | Choose 2 |
| Round positioning | 1. new product expansion; 2. consolidation/final polish round; 3. backend reliability round | Choose 2 |
| Coverage | 1. only one page; 2. key high-frequency operations paths; 3. every frontend route | Choose 2 |
| Primary polish axis | 1. decorative visual refresh; 2. density, consistency, Chinese copy, and responsiveness; 3. marketing-style redesign | Choose 2 |
| Verification method | 1. manual glance only; 2. Playwright smoke screenshots plus browser-style layout assertions where practical; 3. full visual regression platform | Choose 2 |
| Backend scope | 1. frontend-only hardening; 2. add new APIs; 3. add backend preference sync | Choose 1 |
| Copy scope | 1. only new strings; 2. high-frequency operator-visible copy Chinese-first; 3. full i18n framework | Choose 2 |
| Responsive rule | 1. desktop only; 2. 375 / 768 / 1440 checks with no uncontrolled body overflow; 3. custom mobile redesign for every table | Choose 2 |
| Visual style | 1. gradients and hero sections; 2. compact workbench panels using existing `--app-*` tokens; 3. one-off page skins | Choose 2 |

## Requirements

### R1. Key Path Visual QA Matrix

Audit and harden the key operations paths:

- Login
- Protected app shell and navigation
- `今日工作` / cockpit landing surface
- Jobs workbench
- Translation QA queue
- Translation QA review drawer and shared review panel
- Incident triage workbench
- Incident diagnostic drawer
- Job detail diagnostic and Translation QA sections
- Global command palette
- Workbench table settings panel

Each path should be checked for:

- visual consistency with the current workbench style
- readable density
- no avoidable overlapping text or controls
- predictable primary and secondary actions
- stable panel, drawer, popover, and table behavior
- no uncontrolled document/body horizontal overflow

### R2. Chinese-First Operator Copy Sweep

High-frequency operator-visible frontend text must be Chinese-first.

Target surfaces:

- workbench page titles, descriptions, tabs, toolbar labels, filters, empty states, loading states, and error states
- command palette labels, placeholders, command groups, and empty states
- table settings labels and validation/recovery text
- QA review drawer, Incident diagnostic drawer, and Job detail diagnostic text
- batch action and batch-result surfaces

Allowed technical tokens:

- `QA`
- `PDF`
- `DOCX`
- `API`
- `Word`
- `DocumentIR`
- `trace_id`
- raw ids, file ids, route/query keys, enum values, event codes, and error codes

Rules:

- Pair raw technical tokens with Chinese context when they are visible to operators.
- Do not rename code identifiers, API fields, route names, test names, or developer comments just for translation.
- Do not introduce a full i18n framework in this round.

### R3. Responsive And Overflow Hardening

The core operations paths must stay usable at:

- `375px` mobile
- `768px` tablet
- `1440px` desktop

Requirements:

- No uncontrolled `document.body` or root document horizontal overflow.
- Wide tables may scroll inside their own table wrapper.
- Fixed and sticky controls must stay inside the viewport.
- Drawers must fit the viewport and keep primary actions reachable.
- Command palette and table settings panel must remain keyboard reachable on mobile.
- Dense headers and queue strips must not stretch into oversized blocks because of shell/grid interaction.

### R4. Interaction Consistency

Normalize interaction quality across target paths.

Requirements:

- Clickable surfaces have clear hover and active feedback.
- Keyboard focus is visible and follows visual order.
- `Esc` closes command palette, drawers, and transient panels where already expected.
- Icon-only controls have accessible labels or tooltips.
- Button hierarchy is predictable: primary action first, destructive actions restrained.
- Hover states must not shift layout.
- Transitions should be subtle and fast, generally `150ms` to `300ms`.

### R5. Loading, Empty, And Error State Consistency

High-frequency operations surfaces should never feel frozen or ambiguous.

Requirements:

- Async waits over roughly `300ms` show a visible loading indicator, skeleton, or existing Element Plus loading state.
- Empty states explain what is missing and what the operator can do next.
- Error states use `ApiErrorAlert` or existing normalized error patterns where appropriate.
- Partial-load failures should not block successfully loaded modules when the page already supports partial results.
- Batch, saved-view, diagnostic, and QA evidence errors should include a clear retry, reload, open-detail, or copy-diagnostic path when available.
- Do not add broad silent fallbacks that hide failed data loads.

### R6. Visual Token And Layout Consistency

Keep the current operations workbench system coherent.

Requirements:

- Use existing `--app-*` colors, spacing, borders, shadows, and radius tokens.
- Keep panels flat or lightly elevated.
- Keep cards only for repeated items, modals, and genuinely framed tools.
- Do not put cards inside cards.
- Do not add hero sections, decorative gradients, gradient blobs, marketing layout, glass effects, or oversized educational copy.
- Prefer compact command headers, dense filters, and stable table wrappers.
- Keep text within its container across target viewports.

### R7. Browser Verification And Smoke Evidence

Add or update browser verification where implementation changes require it.

Expected verification:

- `npm run build` from `frontend/`.
- Targeted Playwright smoke tests or equivalent browser checks for affected paths.
- Screenshot evidence for desktop and mobile when visual layout changes materially.
- Assertions for no uncontrolled body/document overflow on the modified high-frequency paths.
- Assertions for drawer/panel viewport fit when those surfaces are touched.

Existing smoke tests should be reused and extended instead of creating a disconnected test suite.

### R8. Frontend Spec Hardening

If the work reveals stable rules that future frontend tasks should preserve, update `.trellis/spec/frontend/layout-guidelines.md`.

Likely spec additions:

- visual QA checklist for high-frequency workbench paths
- Chinese visible-copy rule for operator-facing surfaces
- explicit responsive breakpoints used for frontend verification
- command palette, drawer, and table settings verification expectations

Do not turn the spec into a full design manual. Record only durable rules that future tasks should follow.

## Acceptance Criteria

- [ ] Login, app shell, cockpit, Jobs, Translation QA, Incidents, Job detail diagnostics, command palette, and table settings are visually checked after implementation.
- [ ] High-frequency operator-visible text is Chinese-first, with only intentional technical token exceptions.
- [ ] Affected paths are checked at `375px`, `768px`, and `1440px`.
- [ ] No modified path has uncontrolled document/body horizontal overflow.
- [ ] Tables that exceed the viewport scroll inside their own wrapper rather than breaking the page.
- [ ] Drawers and transient panels fit the viewport and keep key actions reachable.
- [ ] Hover, active, focus, and `Esc` close behavior are consistent where applicable.
- [ ] Loading, empty, partial-error, and full-error states are explicit and actionable.
- [ ] `frontend/` build passes.
- [ ] Targeted Playwright smoke or equivalent browser checks cover the material UI changes.
- [ ] Frontend layout guidelines are updated if new durable rules are discovered.

## Definition Of Done

- Read `.trellis/spec/frontend/index.md` and `.trellis/spec/frontend/layout-guidelines.md` before implementation.
- Audit current high-frequency operations paths before editing.
- Fix only concrete visual, copy, responsiveness, accessibility, or interaction findings.
- Keep changes frontend-only unless a blocker proves backend data is unavailable.
- Run `npm run build` in `frontend/`.
- Run targeted frontend tests or smoke checks relevant to the edited paths.
- Capture or verify desktop and mobile layout evidence for materially changed screens.
- Review the diff for hidden fallbacks, duplicated layout rules, unrelated refactors, and unintended copy/behavior changes.

## Technical Approach

1. Start with an audit pass over the key path matrix and record concrete findings.
2. Group fixes by surface area: shell/cockpit, list/filter/table workbenches, QA/diagnostic drawers, command palette/table settings, shared styles.
3. Prefer small local fixes and existing shared components over broad global rewrites.
4. Extend existing smoke tests only where they prove the hardening work.
5. Update `.trellis/spec/frontend/layout-guidelines.md` only for durable rules that emerged from implementation.

## Decision (ADR-lite)

**Context**: Rounds one through nine added the main operations workbench capabilities. Continuing to add features before a visual QA pass would increase inconsistency across lists, filters, batch actions, QA, diagnostics, drawers, and responsive states.

**Decision**: Make round ten a frontend-only experience hardening and visual QA round focused on release-readiness for high-frequency operations paths.

**Consequences**: This round should produce fewer new capabilities than prior rounds, but it should reduce UI debt, catch responsive and copy regressions, and improve confidence before future product expansion.

## Out Of Scope

- New business workflows.
- Backend APIs, backend preference sync, or new persisted settings.
- Full i18n framework.
- Full visual regression platform.
- Global CSS rewrite or full theme replacement.
- Large component architecture refactor.
- Full cleanup of low-frequency admin/settings pages unless they directly affect the key path matrix.
- Marketing pages, hero sections, landing-page copy, or decorative redesign.

## Technical Notes

- Relevant spec files:
  - `.trellis/spec/frontend/index.md`
  - `.trellis/spec/frontend/layout-guidelines.md`
- Existing smoke tests:
  - `frontend/tests/smoke/core-flow.spec.ts`
  - `frontend/tests/smoke/operations-cockpit.spec.ts`
  - `frontend/tests/smoke/incident-triage.spec.ts`
  - `frontend/tests/smoke/workbench-table-preferences.spec.ts`
- UI/UX research record:
  - `research/ui-ux-hardening.md`
