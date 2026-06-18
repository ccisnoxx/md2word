# Current State And Third Round Context

## Sources Inspected

- Trellis context: `python3 ./.trellis/scripts/get_context.py`, `--mode phase`, `--mode packages`.
- First round PRD: `.trellis/tasks/archive/2026-06/06-18-frontend-saas-main-flow-ui/prd.md`.
- Second round PRD and research:
  - `.trellis/tasks/archive/2026-06/06-18-frontend-saas-qa-settings-ui/prd.md`
  - `.trellis/tasks/archive/2026-06/06-18-frontend-saas-qa-settings-ui/research/round1-acceptance-and-second-round-context.md`
- Frontend guidelines:
  - `.trellis/spec/frontend/index.md`
  - `.trellis/spec/frontend/ui-system-guidelines.md`
- Third round target files:
  - `frontend/src/pages/SystemStatusPage.vue`
  - `frontend/src/pages/OpsDashboardPage.vue`
  - `frontend/src/pages/AuditLogPage.vue`
  - `frontend/src/pages/FileRetentionPage.vue`
  - `frontend/src/router/index.ts`
  - `frontend/src/styles/main.scss`

## Second Round Acceptance Evidence

Second round implementation commit reviewed:

- `2862fbef feat: polish translation qa and settings UI`
- Archive commit: `52abd931 chore(task): archive 06-18-frontend-saas-qa-settings-ui`

Changed files in the implementation commit:

- `.trellis/spec/frontend/ui-system-guidelines.md`
- `frontend/src/components/ConfigTodoSummary.vue`
- `frontend/src/pages/SettingsHomePage.vue`
- `frontend/src/pages/TranslationQaQueuePage.vue`
- `frontend/src/pages/TranslationResultQaPage.vue`
- `frontend/src/styles/main.scss`

Observed acceptance evidence from current source:

- `TranslationQaQueuePage` uses `app-page`, `app-page-header`, `app-page-shell`, `app-metric-grid`, `app-metric-card`, `app-panel-card`, and `app-table-card`.
- `TranslationResultQaPage` uses the shared page shell, metric grid, panel card, table card, and subpanel helpers while preserving `documentJobsApi.get`, `documentJobsApi.getTranslationQa`, `updateTranslationQa`, readonly control from `qa.available`, and queue return query handling.
- `SettingsHomePage` and `ConfigTodoSummary` use shared shell, entry card, metric, panel, and subpanel helpers while preserving `configSummaryApi.get("overview")`, `getGroup(groupId, "full")`, `CACHE_TTL_MS`, `RoleGate`, deferred group details, release gate route mapping, and settings entry routes.
- `rg` over the second-round target files shows shared `app-*` helpers are now the dominant visual vocabulary; hardcoded palette values are concentrated in `frontend/src/styles/main.scss` tokens rather than page-local styles.
- `npm run build` from `frontend/` passed on current HEAD. Vite emitted only third-party pure annotation warnings and a large chunk warning.

Build command:

```bash
cd frontend && npm run build
```

Build result:

- `vue-tsc --noEmit` passed.
- `vite build` passed.
- Known warnings: Rollup cannot interpret two third-party `/* #__PURE__ */` annotations from `@vueuse/core`, and the built JS chunk is larger than 500 kB.

## Second Round Residual Issues

- Browser or smoke validation was not re-run in this planning turn. The previous second-round research noted local headless Chrome failed before page assertions, so visual/browser coverage remains weaker than build/type evidence.
- The second round intentionally excluded `SystemStatusPage`, `OpsDashboardPage`, `AuditLogPage`, and `FileRetentionPage`; those pages still use older local page shell, card, table, alert, and status styles.
- The second round did not establish a unified operations information hierarchy for health state, alerts, evidence, timestamps, tables, and dangerous operations. That is the third round's main purpose.

## Third Round Current-State Findings

### Routes And Permissions

`frontend/src/router/index.ts` defines the third round routes under the authenticated app shell:

- `/system-status` -> `SystemStatusPage`, permission `system:read`
- `/system-status/ops-dashboard` -> `OpsDashboardPage`, permission `system:read`
- `/system-status/audit-events` -> `AuditLogPage`, permission `system:read`
- `/system-status/file-retention` -> `FileRetentionPage`, permission `system:read`

These routes should not change in this round.

### SystemStatusPage

- Current page purpose: admin-only readonly overview for backend health, metrics, worker, storage, queue, audit total, and default resources.
- API behavior: `loadStatus` calls `healthApi.getReady()` and `healthApi.getMetrics()` in parallel.
- Current UI: local `system-status-page`, `page-heading`, `overview-grid`, `overview-card`, `readiness-card`, `status-alerts`, `status-panels`, `status-panel`, and hardcoded colors such as `#2563eb`, `#111827`, `#667085`, `#d9e2ec`, `#16a34a`, `#d97706`, `#dc2626`.
- Third round opportunity: convert to shared shell and operations metric/status helpers, keep readiness derivation and links to audit, file retention, ops dashboard, failed jobs, and running jobs unchanged.

### OpsDashboardPage

- Current page purpose: admin-only operations status, fake controls, safety panels, recovery preview, alert delivery, integration capability gates, provider cancellation, S3 delete adapter contracts, and document job recovery actions.
- Size/risk: about 3155 lines. This is the highest-risk page because it contains many safety gates and action flows.
- API behavior includes:
  - readonly status calls: `healthApi.getReady`, `healthApi.getMetrics`, `healthApi.getOpsAlerts`, `opsIntegrationCapabilitiesApi.get`, `opsRecoveryActionsApi.list`, adapter contract calls, and filtered `documentJobsApi.list`.
  - recovery flows: `opsRecoveryActionsApi.preview`, `opsRecoveryActionsApi.execute`, and existing `documentJobsApi.retry`, `cancel`, `archive` after confirmation.
  - alert delivery flows: preview, fake send, controlled real-send preview, controlled real-send, and destination dry-run.
  - provider cancellation and S3 delete preview/fake flows.
- Current UI: local `page-heading`, `summary-grid`, `summary-card`, `alert-grid`, many `dashboard-panel` and contract panel classes, local hardcoded colors, and repeated panel/table/safety patterns.
- Third round opportunity: unify high-level page shell, summary, alert, safety evidence, table, and action panel visuals without altering safety checks, confirmation text, payload builders, exact target lists, dry-run semantics, or real-send gates.

### AuditLogPage

- Current page purpose: admin-only audit event search, structured details drawer, current-page CSV export, and governed filtered export.
- API behavior: `auditEventsApi.list(queryParams.value)` and `auditEventsApi.exportCsv(exportQueryParams.value)`.
- Browser-only export behavior: current page export builds deterministic CSV in the browser with stable sorted details JSON.
- Current UI: local `page-heading`, `filter-section`, `audit-table-section`, drawer detail sections, and hardcoded colors.
- Third round opportunity: convert filters, table panel, pagination, export actions, and details drawer to the shared SaaS layer while preserving query construction, CSV escaping, export filenames, messages, and drawer behavior.

### FileRetentionPage

- Current page purpose: admin-only file library, capacity policy, retention governance, cleanup preview/execute, scheduler dry-run, durable cleanup history, and retention policy governance.
- Size/risk: about 2484 lines. It includes irreversible or safety-sensitive operations.
- API behavior includes:
  - library search, retention plan, storage usage, quota dry-run, quota ops summary, cleanup scheduler dry-run, cleanup history, retention policies.
  - metadata-only mark-expired.
  - physical delete preview and execute gated by selected file IDs, reason, and confirmation phrase.
  - cleanup run preview and execute gated by preview hash, signed plan, reason, and confirmation phrase.
  - retention policy create/update/publish/set-default/disable with reason prompts.
- Current UI: local `page-heading`, `file-workspace-nav`, `file-workspace-tab`, `retention-table-section`, `summary-card`, `quota-result-card`, `safety-grid`, scheduler/delete dialog styling, and many hardcoded colors.
- Third round opportunity: unify workspace tabs, section hierarchy, table cards, dry-run result cards, safety flags, destructive dialogs, loading, empty, and error states while preserving every payload, confirmation, preview hash, signed plan, route tab behavior, and safety tag logic.

## UI Research Notes

`ui-ux-pro-max` design-system search for internal operations UI returned a generic real-time monitoring pattern but recommended an OLED dark theme and a new font. This is not adopted because the project already has a confirmed light Stripe / Linear-style SaaS layer and the user explicitly asked to reuse the first/second round visual system.

Relevant retained guidance:

- Show skeleton/spinner feedback for async operations and avoid blank loading states.
- Error messages should be visible and recoverable, not color-only.
- Empty states should state why the table is empty and what action is available, when there is a useful next step.
- Avoid mobile-breaking horizontal interaction patterns; dense tables can use controlled horizontal scroll.
- Keep visible focus and hover states without layout-shifting effects.

## Planning Implications

- The third round should extend existing `--app-*` tokens and shared page helpers rather than add a new UI library, icon set, font, or theme.
- Shared operations helpers may be worth adding to `frontend/src/styles/main.scss` if they remove repeated local status, alert, safety, metric, table, and action-panel styling across the four target pages.
- `OpsDashboardPage` and `FileRetentionPage` should be treated as safety-sensitive presentation work. The implementation should avoid touching API calls, payload builders, confirmation phrases, preview/execution guards, safety booleans, and destructive-operation availability checks unless a visual change absolutely requires adjacent markup changes.
- Browser visual validation is still desirable, but the minimum gate for this planning stage is current build evidence. Implementation should run `cd frontend && npm run build` and only run browser smoke using an already available browser.
