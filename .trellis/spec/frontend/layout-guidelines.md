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

## Tables And Actions

- Put the scannable entity identity in the first meaningful column.
- Keep low-frequency row actions in an overflow menu; expose only the primary action inline.
- Keep table wrappers horizontally scrollable on mobile instead of forcing a full card-list rewrite unless the task explicitly asks for it.

## Required Verification

For page-level layout changes:

- Run `npm run build` from `frontend/`.
- Capture or inspect affected pages at `1440px` and `375px`.
- Assert no uncontrolled document/body horizontal overflow.
- Assert fixed or sticky action bars fit in the viewport.
- For grid-root workbench pages, assert compact header/queue elements do not stretch beyond their intended content height.

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
