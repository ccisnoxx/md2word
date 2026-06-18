# Frontend SaaS UI Third Round Ops Status Audit Retention

## Design Brief

- Product/workflow: md2word internal admin operations pages under `/system-status`.
- Visual source: reuse the first and second round Stripe / Linear-style light SaaS layer in `frontend/src/styles/main.scss` and the shared `app-*` page helpers.
- Interactivity: full existing interactivity must remain functional. This round is presentation and information hierarchy work, not a behavior redesign.

## Second Round Acceptance And Residual Issues

Acceptance conclusion: the second round is complete enough to serve as the baseline for the third round.

Evidence:

- Second round implementation commit `2862fbef feat: polish translation qa and settings UI` touched the intended QA/settings files and shared style/spec files.
- Archived task `.trellis/tasks/archive/2026-06/06-18-frontend-saas-qa-settings-ui/` contains the second round PRD and research context.
- `TranslationQaQueuePage`, `TranslationResultQaPage`, `SettingsHomePage`, and `ConfigTodoSummary` now use the shared shell, metric, panel, table, entry-card, and subpanel helpers from the first round.
- Key behavior in the second round target pages remains anchored to the existing API calls, route query handling, role gate, cache TTL, deferred loading, save payloads, and queue return context.
- `cd frontend && npm run build` passed on current HEAD. The only observed warnings were existing-style third-party pure annotation warnings and a large chunk warning from Vite.

Residual issues carried forward:

- Browser/smoke visual validation was not re-run in this planning pass; previous local headless Chrome attempts failed before page assertions.
- The second round intentionally excluded system status, ops dashboard, audit log, and file retention. Those pages still have local page shells, repeated cards/tables, hardcoded colors, and inconsistent state hierarchy.
- Operations pages do not yet share one clear information hierarchy for health status, alerts, evidence, tables, timestamps, and actions.

Full evidence is in `research/current-state.md`.

## Goal

Complete the third frontend productization round by bringing the admin operations pages into the same SaaS visual system established in the first and second rounds. The result should make operational health, alerts, evidence, audit data, retention status, timestamps, and actions easier to scan while preserving all existing backend contracts and safety behavior.

## What I Already Know

- The frontend stack is Vue 3, Element Plus, Vue Router, SCSS, and existing `--app-*` tokens.
- The project has explicit frontend guidelines in `.trellis/spec/frontend/index.md` and `.trellis/spec/frontend/ui-system-guidelines.md`.
- The target routes are:
  - `/system-status`
  - `/system-status/ops-dashboard`
  - `/system-status/audit-events`
  - `/system-status/file-retention`
- All four target routes are under `system:read` permission in `frontend/src/router/index.ts`.
- Target pages are currently presentation-heavy and already contain loading flags, API errors, table empty text, safety messages, and confirmation flows. The third round should standardize those surfaces, not replace their logic.
- `OpsDashboardPage` and `FileRetentionPage` are large and safety-sensitive. They contain fake/real delivery gates, dry-run previews, destructive action confirmations, preview hashes, signed plans, exact target checks, and audit/safety evidence.
- This round must not introduce a new UI library, replace Element Plus, change API payloads, or deep-redesign all configuration detail pages.

## Requirements

### Shared Operations Information Hierarchy

- Reuse the existing `app-page`, `app-page-shell`, `app-page-header`, `app-panel`, `app-panel-card`, `app-table-card`, `app-metric-grid`, `app-metric-card`, `app-entry-card`, and `app-subpanel` vocabulary where it fits.
- Establish a consistent operations reading order across target pages:
  1. page title and primary refresh/export/action controls
  2. health or summary status
  3. blocking alerts and warnings
  4. evidence panels and safety notes
  5. filters, tables, timestamps, and detailed records
  6. guarded operations and confirmation-dependent actions
- Use one status severity language across the round:
  - ready/success uses `--app-color-success`
  - warning/degraded/needs attention uses `--app-color-warning`
  - blocked/error/destructive risk uses `--app-color-danger`
  - unknown/info/readonly/dry-run evidence uses `--app-color-info` or muted tokens
- Unify empty, loading, error, readonly, dry-run, and unavailable states. Use existing `ApiErrorAlert`, Element Plus loading states, and table empty text rather than inventing hidden fallback behavior.
- Preserve dense internal-tool information density. Do not turn operations pages into marketing pages, hero layouts, or decorative card grids.

### SystemStatusPage

- Convert the page root and header to the shared SaaS shell.
- Rework readiness summary, application/deployment/metrics/audit cards, blockers/warnings, backend/worker/storage descriptions, queue metrics, and resource versions to shared metric/panel/table helpers.
- Keep the existing readonly behavior:
  - `healthApi.getReady()` and `healthApi.getMetrics()` remain the source of truth.
  - readiness derivation from dependency checks remains unchanged.
  - links to audit logs, file retention, ops dashboard, failed jobs, and running jobs remain unchanged.
- Keep the page clearly readonly. Do not add new execution controls.

### OpsDashboardPage

- Convert the page root, header, summary cards, alert list, integration capability panel, alert delivery panel, safety evidence, recovery preview, provider/S3 contract sections, and job tables to the shared visual system.
- Preserve all existing operation semantics:
  - readonly dashboard data loading via health, ops alerts, integration capability, recovery action, adapter contract, provider cancellation, and document job list APIs.
  - recovery preview before execution.
  - `documentJobsApi.retry`, `cancel`, and `archive` usage for existing task actions.
  - `opsRecoveryActionsApi.execute` for replay.
  - fake delivery, controlled real-send preview, real-send gate, destination dry-run, provider cancellation preview/fake, and S3 delete preview/fake behavior.
  - all confirmation text, exact target lists, safety booleans, dedupe window handling, selected alert code handling, and disabled conditions.
- Improve visual grouping so operators can distinguish readonly evidence, dry-run preview, fake execution, controlled real execution, and dangerous/destructive risk.
- Do not add new real operation buttons or weaken any gate.

### AuditLogPage

- Convert the page root, header actions, filter form, filter buttons, table panel, pagination, drawer sections, JSON/details display, loading, empty, and error states to the shared visual system.
- Preserve audit behavior:
  - `auditEventsApi.list(queryParams.value)` remains the list source.
  - `auditEventsApi.exportCsv(exportQueryParams.value)` remains the filtered export source.
  - current-page export remains browser-side and keeps stable sorted details JSON.
  - CSV escaping, generated filenames, truncated export warning, success messages, drawer opening, and details formatting remain unchanged.
- Make filters and export controls scan cleanly at desktop widths and degrade to a readable stacked layout on narrow screens.

### FileRetentionPage

- Convert the page root, header, workspace tabs, library search, capacity/policy sections, quota dry-run, quota ops, retention governance, cleanup actions, scheduler dry-run, cleanup history, reports, dialogs, safety flags, and tables to the shared visual system.
- Preserve file retention behavior:
  - library search, retention plan, storage usage, quota policy dry-run, quota ops summary, cleanup scheduler dry-run, cleanup history, and retention policies remain backed by existing `filesApi` calls.
  - mark-expired remains metadata-only and keeps its confirmation.
  - physical delete requires the selected file preview, matching current selection, reason, and backend confirmation phrase.
  - cleanup run execute requires preview hash, signed plan, reason, and confirmation phrase.
  - policy publish, set-default, and disable continue to require reason prompts.
  - route tab behavior and current query handling remain unchanged.
- Make destructive or irreversible areas visually explicit without increasing alarm noise everywhere else.
- Do not expose object keys, local paths, bucket/checksum/etag, raw metadata, or file contents.

### Shared Components And Styles

- Prefer adding a small number of reusable SCSS helpers in `frontend/src/styles/main.scss` if the same operations metric/status/safety/table/action pattern appears across two or more target pages.
- Keep helpers semantic and project-level; avoid a second operations-only design token namespace unless a value is truly operations-specific.
- Use Element Plus icons already available in the project if markup needs icon alignment. Do not add lucide, heroicons, chart libraries, or a new UI package.
- If new shared helpers become part of the local UI system, update `.trellis/spec/frontend/ui-system-guidelines.md`.

### Behavior Preservation

- Do not modify API clients, API payloads, route definitions, permission metadata, Pinia stores, auth guards, backend action availability, upload flow, polling flow, error normalization, CSV semantics, confirmation phrases, preview hashes, signed plans, or destructive-operation guards.
- Do not add silent fallbacks, suppress errors, hide backend-provided safety evidence, or replace backend availability with frontend guesses.
- Do not weaken existing tests or smoke expectations. If a test needs an update because visible copy/structure changed, keep its business assertion at least as strong.

## Acceptance Criteria

- [ ] `SystemStatusPage` uses the shared page shell and shared status/metric/panel helpers while preserving `healthApi.getReady`, `healthApi.getMetrics`, readiness derivation, readonly links, and refresh behavior.
- [ ] `OpsDashboardPage` uses the shared visual layer for summary, alerts, safety evidence, tables, and operation panels while preserving all preview, fake, real-send, recovery, confirmation, exact-target, disabled-state, and payload behavior.
- [ ] `AuditLogPage` uses the shared visual layer for header actions, filters, table, pagination, drawer, JSON/details, loading, empty, and error states while preserving list/export queries, current-page CSV generation, filtered CSV export, and drawer behavior.
- [ ] `FileRetentionPage` uses the shared visual layer for workspace tabs, filters, tables, dry-run panels, safety flags, retention policy governance, cleanup reports, scheduler dry-run, history, and destructive dialogs while preserving every retention, quota, cleanup, policy, preview, and execute contract.
- [ ] The four target pages use consistent status colors and alert severity mapping through `--app-*` semantic tokens or shared helpers.
- [ ] Empty states, loading states, API errors, readonly/dry-run notices, and destructive warnings are visible and consistent across the target pages.
- [ ] Dense tables remain readable at approximately 375px, 768px, 1024px, and 1440px. Controlled horizontal table scrolling is acceptable; incoherent text overlap or crushed action buttons are not.
- [ ] No new UI library, icon library, chart library, font import, theme system, or Element Plus replacement is introduced.
- [ ] This round does not deep-redesign settings detail pages, translation workbenches, term proposal flows, login, job main flow, or backend behavior.
- [ ] `cd frontend && npm run build` passes after implementation.
- [ ] If a usable local browser is available, a browser/manual smoke covers at least the four target routes. If no usable browser is available, the implementation result records the blocker and uses build/source inspection as the fallback.

## Definition Of Done

- User confirms this PRD before `task.py start` or implementation begins.
- Implementation reads this PRD, `research/current-state.md`, `.trellis/spec/frontend/index.md`, and `.trellis/spec/frontend/ui-system-guidelines.md`.
- Code changes stay scoped to the four target pages, necessary shared SCSS helpers, and optional frontend UI guideline updates.
- `cd frontend && npm run build` is run and passes.
- `npx playwright install chromium` is not run.
- Browser validation uses an already available in-app Browser, Chrome plugin, CDP, or local browser only. If unavailable, the final implementation report states the skipped coverage and residual risk.
- Final implementation report states whether comments, docstrings, or docs were updated. For pure style changes, it should explicitly say no business comments were needed unless shared UI guidelines changed.

## Technical Approach

Recommended approach: continue the first and second round pattern of shared CSS helpers plus page-local markup cleanup. Do not introduce a new Vue layout abstraction or component library in this round.

- Shared style work:
  - Extend `main.scss` only for patterns repeated across the third round pages, such as operations status summary cards, alert stacks, safety evidence chips, table panels, action strips, filter shells, and report cards.
  - Map local hardcoded colors to existing `--app-color-*` tokens.
  - Keep radii at `--app-radius-md` or less, matching the current UI system.

- Page migration order:
  1. `SystemStatusPage` as the smallest operations baseline.
  2. `AuditLogPage` to establish filter/table/drawer conventions.
  3. `OpsDashboardPage` with careful section-by-section visual conversion.
  4. `FileRetentionPage` with careful section-by-section visual conversion and special attention to destructive dialogs.

- Risk controls:
  - Treat `OpsDashboardPage` and `FileRetentionPage` as safety-sensitive. Prefer class/template changes and token replacements over script changes.
  - If a script change becomes necessary, it must be directly tied to presentation state and must not alter API calls, payload builders, guards, confirmations, safety checks, or route behavior.
  - Use `rg` before changing repeated classes or tokens, then migrate all intended occurrences consistently.

## Decision (ADR-lite)

**Context**: The first two rounds created and applied a light internal SaaS visual layer to the main job flow, Translation QA, and settings entry pages. The remaining operations pages are still visually fragmented and safety-heavy.

**Decision**: The third round will reuse the existing `--app-*` token system and add only small shared SCSS helpers where repeated operations surfaces justify them. The work is presentation-focused and preserves all operational behavior.

**Consequences**: This keeps implementation risk low and maintains Element Plus compatibility. The tradeoff is that very large pages such as `OpsDashboardPage` and `FileRetentionPage` may still contain page-local structure after this round, but their visible hierarchy and status language should align with the rest of the product.

## Implementation Plan

- Step 1: Add or refine shared operations helpers in `main.scss`, then migrate `SystemStatusPage`.
- Step 2: Migrate `AuditLogPage` filters, table, pagination, export actions, and details drawer.
- Step 3: Migrate `OpsDashboardPage` section by section, preserving safety gates and action flows.
- Step 4: Migrate `FileRetentionPage` section by section, preserving retention, cleanup, quota, policy, and destructive confirmation flows.
- Step 5: Run build, inspect diff for behavior changes, and attempt browser validation only with an available existing browser/tool.

## Research References

- `research/current-state.md` - second round acceptance evidence, current operations page findings, UI research notes, and implementation risks.

## Out Of Scope

- No new UI library, icon library, chart library, font import, or Element Plus replacement.
- No backend/API/client/router/permission/store refactor.
- No changes to destructive operation contracts, confirmation phrases, preview hash flow, signed plan flow, exact-target checks, or safety evidence.
- No deep redesign of all configuration detail pages.
- No redesign of job main flow, Translation QA, term proposal/workbench, login, or settings detail pages except passive global helper effects.
- No new dark mode effort, theme switcher, charting system, animations, white-label system, or landing-page treatment.

## Open Questions

- 请确认本 PRD 是否可以作为第三轮实现依据。推荐确认当前范围：只做 `SystemStatusPage`、`OpsDashboardPage`、`AuditLogPage`、`FileRetentionPage` 及必要共享样式/运维状态组件的视觉产品化，不改变任何运维行为或安全 gate。
