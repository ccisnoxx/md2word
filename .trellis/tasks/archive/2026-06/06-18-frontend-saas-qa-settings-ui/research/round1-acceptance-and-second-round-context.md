# Round 1 Acceptance And Second Round Context

## Round 1 Acceptance Summary

First round task: `.trellis/tasks/archive/2026-06/06-18-frontend-saas-main-flow-ui/`

Implementation commit reviewed: `c56793a0 feat: polish document job main flow UI`

Changed files in the implementation commit:

- `frontend/src/styles/main.scss`
- `frontend/src/layouts/AppLayout.vue`
- `frontend/src/pages/JobsPage.vue`
- `frontend/src/pages/JobCreatePage.vue`
- `frontend/src/pages/JobDetailPage.vue`
- `frontend/src/components/JobTable.vue`
- `frontend/src/components/PdfUploadPanel.vue`
- `frontend/src/components/JobActions.vue`
- `frontend/src/components/JobStatusBadge.vue`
- `frontend/src/components/JobProgress.vue`

Observed acceptance evidence:

- `frontend/src/styles/main.scss` now defines semantic `--app-*` tokens for surface, border, text, primary, semantic status colors, radius, spacing, shadows, content widths, and shell classes.
- `JobsPage`, `JobCreatePage`, and `JobDetailPage` use the shared page shell/header vocabulary such as `app-page`, `app-page-shell`, `app-page-header`, `app-panel`, `page-title`, and `page-description`.
- `JobStatusBadge`, `JobProgress`, `JobActions`, `JobTable`, and `PdfUploadPanel` now consume the shared visual tokens for density, status colors, borders, radius, and text hierarchy.
- The first round implementation commit touched the intended main-flow UI files and did not include API, store, router, backend, or data contract files.
- `cd frontend && npm run build` passed on 2026-06-18. Vite emitted only existing-style warnings about third-party pure annotations and chunk size; there was no type-check or build failure.

Smoke/browser validation:

- Attempted: `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" npm run test:smoke`
- Result: all 10 smoke tests failed before any page assertion, at `browserType.launch` with `Target page, context or browser has been closed`.
- Direct probe: `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome --headless --disable-gpu --no-sandbox --dump-dom data:text/html,...` exited `134`.
- Interpretation: the local browser/headless environment is blocked or incompatible for this session. This does not prove a UI behavior regression, but it leaves visual/browser smoke coverage unverified.

Round 1 residual risks:

- Main-flow visual layout was not verified through an actual rendered browser at 375px, 768px, 1024px, and 1440px in this session because headless Chrome could not launch.
- Existing smoke coverage is broad and includes second-round target routes, but it cannot currently provide regression evidence until the local browser launch issue is resolved.
- The first round intentionally did not redesign Translation QA, Settings, system status, or configuration detail pages. Those pages now sit behind the improved `AppLayout`, but their page-level surfaces still use older local styles.

## Second Round Current-State Findings

Target files inspected:

- `frontend/src/pages/TranslationQaQueuePage.vue`
- `frontend/src/pages/TranslationResultQaPage.vue`
- `frontend/src/pages/SettingsHomePage.vue`
- `frontend/src/components/ConfigTodoSummary.vue`
- `frontend/src/router/index.ts`
- `frontend/tests/smoke/core-flow.spec.ts`
- `.trellis/spec/frontend/index.md`
- `.trellis/spec/frontend/ui-system-guidelines.md`

Findings:

- `TranslationQaQueuePage` uses its own `.page-heading`, `.metric-card`, `.queue-panel`, table, toolbar, pagination, and hardcoded colors such as `#2563eb`, `#111827`, `#667085`, `#d9e2ec`, and `#ffffff`.
- `TranslationResultQaPage` uses local grid, metric, card, trace, and text styles with hardcoded color/border values. It has a dense evidence workflow that should be visually organized without changing QA editability or API behavior.
- `SettingsHomePage` is already an important configuration-center entry page, but it uses local heading, card, release gate, group, finding, and action-link styles instead of the first-round shell and tokens.
- `ConfigTodoSummary` is rendered directly on `SettingsHomePage` and carries local metric card/border/text styling. It should be included as part of the settings entry-page polish.
- `frontend/src/router/index.ts` shows the requested target routes:
  - `/translation-qa` -> `TranslationQaQueuePage`
  - `/jobs/:jobId/translation-qa` -> `TranslationResultQaPage`
  - `/settings` -> `SettingsHomePage`
- Existing smoke tests cover these target routes:
  - translation QA queue inspection
  - readonly unavailable QA result
  - settings entry and settings detail route access

## UI Research Notes

`ui-ux-pro-max` design-system search returned a generic minimal single-column/landing pattern with black and gold colors. That result is not adopted because the task is an internal SaaS workbench, not a marketing page.

Useful checklist items retained from the UI research:

- Avoid mobile-breaking tables; use horizontal scroll wrappers or dense responsive layout.
- Keep form labels associated and visible; do not rely on placeholders only.
- Preserve explicit loading, success, error, readonly, and unavailable states.
- Check 375px, 768px, 1024px, and 1440px layouts when browser tooling is available.
- Maintain visible hover/focus states and avoid layout-shifting hover effects.

## Planning Implications

- Second round should reuse the first-round `--app-*` visual layer instead of inventing page-local QA/settings tokens.
- It is acceptable to add a small number of shared SCSS helper classes to `main.scss` if the same metric card, table shell, form shell, alert/action area, or entry-card pattern appears across target pages.
- It is not necessary to create new Vue layout abstractions for this round unless CSS-only reuse becomes unclear or duplicative.
- The implementation should not touch system status, ops dashboards, file retention, all settings detail pages, or term proposal/workbench pages except through passive global token effects.
