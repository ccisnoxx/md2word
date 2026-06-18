# UI System Guidelines

## Scope

These rules apply to `frontend/src/styles/main.scss`, `frontend/src/layouts/AppLayout.vue`, and the completed productized workbench pages/components under `frontend/src/pages/` and `frontend/src/components/`.

## Final SaaS Workbench Design System

The accepted md2word frontend direction is a Stripe / Linear-like internal SaaS workbench: dense, calm, data-first, and task-oriented. The UI should optimize for scanning operational state, filtering records, reviewing evidence, and executing guarded actions.

The `ui-ux-pro-max` design-system generation for md2word classified the product as a data-dense drill-down SaaS dashboard. Keep that pattern, but normalize visual choices to this project's existing `--app-*` tokens rather than importing an external palette, font stack, or UI library.

### Visual Baseline

- Product pattern: data-dense workbench with drill-down pages, not a marketing site or landing-page hero.
- Tone: restrained neutral surfaces, clear blue primary actions, semantic success/warning/danger/info states, low decoration.
- Typography: use `--app-font-sans` and `--app-font-mono`; do not add remote font imports for productization polish.
- Layout: shared page shells, compact headers, metric cards, tables, filters, evidence panels, and action rows.
- Effects: stable hover/focus states, table row hover, visible focus rings, no scale-based hover shifts.
- Responsive rule: pages must remain usable at roughly 375px, 768px, 1024px, and 1440px. Dense tables may scroll inside their own containers, but the page itself should not create incoherent horizontal overflow.

### Covered Workbench Areas

The shared visual system applies to the completed frontend productization surface:

- Main document job flow: `/jobs`, `/jobs/new`, `/jobs/:jobId`
- Translation QA: `/translation-qa`, `/jobs/:jobId/translation-qa`
- Settings entry: `/settings` and `ConfigTodoSummary`
- System and operations: `/system-status`, `/system-status/ops-dashboard`, `/system-status/audit-events`, `/system-status/file-retention`
- Configuration center: template list/detail and Word page style list/detail pages
- Terminology and translation governance: term rule set/workbench, translation profiles, translation term sets, and proposal review pages

### Final Audit Categories

- Conforming: pages use shared `app-page`, `app-page-shell`, `app-page-header`, panel/table/filter/evidence helpers, `--app-*` tokens, Element Plus controls, and existing route/API/permission behavior.
- Acceptable deviation: large governance and operations pages may retain page-local grid names where they express page-specific layout, as long as surfaces use shared helpers and tokens.
- P0/P1 repair boundary: only fix issues that block route entry, break auth/permission/API behavior, create unreadable or overlapping primary workflows, hide safety evidence, alter guarded actions, or cause unhandled runtime errors.
- P2 follow-up boundary: cosmetic cleanup such as reducing remaining local class names, trimming bundle size, or improving browser tooling reliability should not trigger a fifth productization round by itself.
- No-redo rule: do not replace the Vue 3 + Element Plus + SCSS stack, do not add a new UI kit or icon library, and do not rebuild pages that already satisfy the shared workbench contract.

## Convention: Project Visual Tokens

**What**: Shared UI values live in `frontend/src/styles/main.scss` as semantic CSS variables prefixed with `--app-*`.

**Why**: Main-flow pages previously carried page-local color, spacing, radius, border, and shadow values. Reusing semantic tokens keeps `/jobs`, `/jobs/new`, and `/jobs/:id` visually consistent without replacing Element Plus.

**Good**:

```scss
.upload-card {
  border: 1px solid var(--app-color-border);
  border-radius: var(--app-radius-md);
  background: var(--app-color-surface);
  box-shadow: var(--app-shadow-panel);
}
```

**Bad**:

```scss
.upload-card {
  border: 1px solid #d9e2ec;
  border-radius: 8px;
  background: #ffffff;
  box-shadow: 0 8px 22px rgba(15, 23, 42, 0.06);
}
```

## Convention: Page Shell Classes

**What**: Use shared classes for repeated product shell patterns:

- `app-page`
- `app-page-shell`
- `app-page-shell--wide`
- `app-page-shell--narrow`
- `app-page-header`
- `app-panel`
- `page-kicker`
- `page-title`
- `page-description`
- `app-panel-card`
- `app-table-card`
- `app-metric-grid`
- `app-metric-card`
- `app-entry-card`
- `app-subpanel`
- `app-status-card`
- `app-status-dot`
- `app-alert-stack`
- `app-filter-panel`
- `app-evidence-panel`
- `app-action-row`
- `app-split-grid`
- `app-review-grid`
- `app-governance-grid`
- `app-governance-metric`
- `app-technical-block`
- `app-inline-meta`
- `app-compact-grid`
- `app-compact-card`
- `app-key-value-list`
- `app-key-value-row`
- `app-workspace-tab`

**Why**: Page-level Vue abstractions are unnecessary for the first UI polish round, but repeated page shells should still share dimensions, padding, borders, hierarchy, and typography.

**Good**:

```vue
<main class="jobs-page app-page" aria-labelledby="jobs-title">
  <section class="jobs-hero app-page-header app-page-shell app-page-shell--wide">
    <p class="page-kicker">Document Jobs</p>
    <h1 id="jobs-title" class="page-title">任务列表</h1>
  </section>
</main>
```

## Convention: Shared Workbench Surfaces

**What**: When a page needs repeated metrics, action rows, split/review grids, governance counters, entry links, table cards, technical evidence blocks, or nested evidence panels, use the shared `app-*` surface helpers from `main.scss` before adding page-local card styles.

**Why**: Translation QA and settings pages previously copied local metric cards, entry cards, and table shell styles. Reusing the shared helpers keeps later productization rounds aligned with the main job flow and prevents hardcoded color drift.

**Good**:

```vue
<section class="app-metric-grid app-page-shell" aria-label="配置状态">
  <article class="app-metric-card">
    <span>阻断配置组</span>
    <strong>{{ blockedGroups }}</strong>
    <small>需要先处理再发布</small>
  </article>
</section>

<el-card class="app-panel-card app-table-card app-page-shell" shadow="never">
  <el-table :data="rows" />
</el-card>

<section class="app-governance-grid" aria-label="发布治理摘要">
  <article class="app-governance-metric">
    <span>可发布</span>
    <strong>{{ publishableCount }}</strong>
  </article>
</section>

<pre class="app-technical-block">{{ payloadPreview }}</pre>
```

**Bad**:

```scss
.metric-card {
  border: 1px solid #d9e2ec;
  border-radius: 8px;
  background: #fff;
}
```

## Convention: Operations Status And Evidence Surfaces

**What**: Operations pages should use the shared status, evidence, filter, compact-card, key-value, and workspace-tab helpers when presenting health, alerts, dry-run evidence, audit tables, or guarded operations.

**Why**: System status, ops dashboard, audit log, and file retention pages share the same information hierarchy: health summary, warnings, evidence, tables, timestamps, and guarded actions. Shared helpers keep severity colors, spacing, empty/loading surfaces, and dense evidence panels consistent without changing Element Plus behavior.

**Good**:

```vue
<article class="app-metric-card app-status-card is-warning">
  <span class="app-status-dot" aria-hidden="true"></span>
  <div>
    <strong>有告警</strong>
    <small>核心 readiness 可用，但存在需要关注的非阻断警告。</small>
  </div>
</article>

<section class="app-filter-panel app-table-card app-page-shell" aria-label="审计日志筛选">
  <el-form label-position="top" />
  <el-table :data="events" />
</section>

<div class="app-evidence-panel">
  <el-tag type="warning" effect="plain">dry_run=true</el-tag>
</div>
```

**Bad**:

```scss
.ops-card {
  border: 1px solid #d9e2ec;
  background: #fbfdff;
}
```

## Element Plus Styling Boundary

**Allowed**: Use scoped `:deep()` rules to make Element Plus controls fit the project visual layer when the rule is local to the page/component.

**Forbidden**: Do not change Element Plus behavior, event wiring, permission conditions, loading flags, or backend-provided action availability while doing presentation-only work.

**Good**:

```scss
.jobs-page :deep(.el-button) {
  border-radius: var(--app-radius-md);
}
```

**Bad**:

```vue
<!-- Do not replace backend action availability with frontend guesses. -->
<el-button :disabled="job.status !== 'succeeded'">下载</el-button>
```

## Main Flow Behavior Contract

Presentation changes to `/jobs`, `/jobs/new`, and `/jobs/:id` must preserve:

- router targets and route query handling
- auth and permission checks
- file validation and upload authorization flow
- document job create payloads
- polling and visibility handling
- download, retry, clone, cancel, archive, unarchive, and delete availability rules
- API error display and diagnostic context

## Quality Checks

- Always run `cd frontend && npm run build` after changing Vue or SCSS.
- Prefer `cd frontend && npm run test:smoke` for main-flow behavior regressions when Playwright Chromium is installed locally.
- If smoke cannot run because browser binaries are missing, state that exact environment blocker and keep `npm run build` as the minimum gate.
