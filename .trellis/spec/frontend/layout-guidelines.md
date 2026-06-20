# Frontend Layout Guidelines

## Scope

These rules apply to protected Vue workbench pages under `frontend/src/pages/`, shared shell styles in `frontend/src/styles/main.scss`, and shared list/table components.

## Page Shell Contract

`main.app-page` provides a minimum viewport height for protected pages. If a page root also uses CSS grid, explicitly pin rows to their content height:

```scss
.example-page {
  display: grid;
  align-content: start;
  grid-auto-rows: max-content;
}
```

Do not rely on the default CSS grid alignment on `main.app-page`. With `min-height` present, default grid alignment can stretch auto rows and turn compact command headers or queue cards into oversized blocks.

## Operations Workbench Surfaces

- Use compact command headers and queue strips for high-frequency operations pages.
- Use existing `--app-*` tokens for color, spacing, borders, shadows, and radius.
- Prefer flat or lightly elevated panels. Avoid broad gradients, glass effects, and decorative grid backgrounds on dense operational pages.
- If a page needs a bottom fixed bulk-action bar, ensure no ancestor transform traps fixed positioning. Page-level entry animation may need to be disabled on that page.

## Personal Cockpit Aggregators

Personal cockpit or landing pages that summarize work across existing queues must be launch surfaces, not second queue implementations:

- Reuse existing page APIs and saved-view query helpers, such as `jobsSavedViewStateToQuery`, `translationQaSavedViewStateToQuery`, and `incidentsSavedViewStateToQuery`.
- Deep links must preserve the destination page's query contract, including drawer parameters like `qa_job_id` and `incident_job_id`.
- Fetch only source modules allowed by the current account permissions, and show partial module errors without blocking successfully loaded queues.
- Keep bulk actions, team assignment, drag/drop customization, realtime push, and BI dashboards in their owning pages or separate features unless the task explicitly changes that contract.

## Page-Level Drawers

Workbench pages that open a right-side detail or review drawer from an in-page list should render the overlay at document level and keep URL state reversible:

```vue
<el-drawer append-to-body :model-value="Boolean(selectedId)" @close="clearSelectedId">
  <SharedReviewPanel @close="clearSelectedId" />
</el-drawer>
```

- Use `append-to-body` when a drawer must cover the protected shell topbar/sidebar and accept pointer events above sticky page controls.
- Store deep-linkable selected rows in a specific query parameter such as `qa_job_id`, and remove only that parameter on close so unrelated filters/search params survive.
- Keep the drawer content in a shared panel component when the same review surface is reused by a queue drawer and a detail page.
- For unavailable or diagnostic-only states, reuse the same panel frame in read-only mode rather than adding a separate visual implementation.

## Dialog Forms

Long workbench forms inside `el-dialog` must own their scroll container in page markup instead of relying only on Element Plus internal body selectors:

```vue
<el-dialog class="example-dialog" append-to="body" :append-to-body="true">
  <div class="example-dialog-scroll">
    <el-form>
      ...
    </el-form>
  </div>
  <template #footer>...</template>
</el-dialog>
```

```scss
.example-dialog-scroll {
  max-height: min(640px, calc(100vh - 220px));
  overflow-y: auto;
  overscroll-behavior: contain;
}
```

This keeps header/footer actions reachable and makes mouse-wheel behavior stable even when the dialog content is teleported by Element Plus.

Workbench pages inherit entry animations that leave a `transform` on `.app-page`. A non-teleported dialog overlay will be fixed relative to that transformed page instead of the viewport; after the page scrolls to a lower action button, the dialog can open partly or completely off screen. Dialogs opened from protected workbench pages must therefore append to `body` and constrain their own height:

```vue
<el-dialog
  class="rule-dialog"
  width="min(760px, calc(100vw - 32px))"
  top="24px"
  append-to="body"
  :append-to-body="true"
>
  <div class="rule-dialog-scroll">...</div>
</el-dialog>
```

```scss
:deep(.rule-dialog) {
  display: flex;
  flex-direction: column;
  max-height: calc(100vh - 48px);
  max-height: calc(100dvh - 48px);
}

:deep(.rule-dialog .el-dialog__body) {
  flex: 1 1 auto;
  min-height: 0;
  overflow: hidden;
}
```

## Tables And Actions

- Put the scannable entity identity in the first meaningful column.
- Keep low-frequency row actions in an overflow menu; expose only the primary action inline.
- Keep table wrappers horizontally scrollable on mobile instead of forcing a full card-list rewrite unless the task explicitly asks for it.

## Operator-Facing Copy

- High-frequency protected workbench surfaces must use Chinese-first visible copy.
- Technical tokens such as `QA`, `PDF`, `DOCX`, `API`, `Word`, `DocumentIR`, `trace_id`, raw ids, enum values, event codes, and error codes may remain visible, but pair them with Chinese context when they are not self-explanatory.
- Do not rename code identifiers, route names, API fields, test names, or developer comments solely for copy cleanup.

## Required Verification

For page-level layout changes:

- Run `npm run build` from `frontend/`.
- Capture or inspect affected pages at `1440px`, `768px`, and `375px`.
- Assert no uncontrolled document/body horizontal overflow.
- Assert fixed or sticky action bars fit in the viewport.
- For grid-root workbench pages, assert compact header/queue elements do not stretch beyond their intended content height.
- For page-level drawers, assert the overlay covers the protected shell, drawer actions are clickable, close removes only the drawer query parameter, and any keyboard shortcuts have visible hints.
- For command palettes, drawers, mobile navigation, and table settings popovers, assert `Escape` closes transient UI where expected and that keyboard-opened controls remain inside the viewport.
- For table settings, verify the popover at mobile/tablet widths as well as desktop; wide tables may scroll only inside their own wrapper.

## Wrong vs Correct

### Wrong

```scss
.qa-page {
  display: grid;
  gap: var(--app-space-3);
}
```

This lets `main.app-page` distribute extra vertical space across auto grid rows.

### Correct

```scss
.qa-page {
  display: grid;
  align-content: start;
  grid-auto-rows: max-content;
  gap: var(--app-space-3);
}
```

This keeps inbox and table layouts compact while preserving the page shell height.

## Protected App Shell

Protected routes use a global sidebar plus compact topbar shell. Keep brand identity in the sidebar, keep page context and breadcrumbs in the topbar, and do not add a separate breadcrumb row between the topbar and business page header.

Desktop sidebar collapse state is a shell preference only. Persist it with `md2word.sidebar.collapsed`; mobile drawer state stays temporary and must not reuse the desktop preference.
