# ui-ux-pro-max design-system research

## Query

`document conversion translation QA operations internal SaaS workbench data dense dashboard`

## Useful findings

- The strongest matching style is **Data-Dense Dashboard**: multiple tables/widgets, KPI cards, compact grids, row hover feedback, filters, and high data visibility.
- This matches the existing project spec direction: an internal SaaS workbench optimized for scanning operational state and executing guarded actions.
- The generated design system recommends blue primary actions, amber highlights, light neutral surfaces, row highlighting, tooltips, filter animations, visible focus states, and responsive checks at 375px, 768px, 1024px, and 1440px.
- Vue-specific guidance emphasizes semantic elements, no `v-if` on the same element as `v-for`, and ARIA state kept in sync with component state.
- UX guidance emphasizes visible focus indicators, hover feedback that is not required for touch use, and clear cursor/interactive feedback.

## Findings rejected or normalized

- The generated **Funnel (3-Step Conversion)** product pattern is landing-page oriented and should not drive protected workbench pages.
- The generated Fira font pairing should not be imported. Project spec requires the existing `--app-font-sans` and `--app-font-mono` tokens.
- The generated palette should be normalized to existing `--app-*` tokens instead of adding a new external color system.

## Implications for md2word

- Keep the Vue 3 + Element Plus + SCSS stack and the shared `app-*` visual helpers.
- Improve polish through hierarchy, spacing, density, tokens, hover/focus states, responsive behavior, and component consistency.
- Do not change route guards, permissions, API calls, upload flow, polling, or backend action availability while doing presentation work.
- Treat login page and protected workbench pages separately: login can be more expressive, while workbench pages should stay dense, calm, and operational.

