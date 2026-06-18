# UI System Guidelines

## Scope

These rules apply to `frontend/src/styles/main.scss`, `frontend/src/layouts/AppLayout.vue`, and the document job main flow pages/components under `frontend/src/pages/` and `frontend/src/components/`.

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

**What**: When a page needs repeated metrics, entry links, table cards, or nested evidence panels, use the shared `app-*` surface helpers from `main.scss` before adding page-local card styles.

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
```

**Bad**:

```scss
.metric-card {
  border: 1px solid #d9e2ec;
  border-radius: 8px;
  background: #fff;
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
