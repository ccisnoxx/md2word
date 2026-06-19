# md2word Operations Workbench Design System

## Purpose

This lightweight design system defines the first redesign pass for the md2word frontend as a high-frequency operations workbench. It is intentionally scoped to planning and implementation guidance; it does not prescribe a full component library rewrite.

## Product Positioning

md2word is an internal document delivery and QA workbench for PDF to DOCX conversion, translation QA, evidence tracking, and operational follow-up. The redesigned frontend should feel like a focused operations inbox, not a marketing SaaS site or decorative dashboard.

## Chosen Direction

* Product type: internal operations workbench.
* Primary workflow: daily handling of failed, stalled, pending QA, and batch-actionable work.
* Density: balanced high density.
* Visual tone: keep the existing indigo/emerald identity, but reduce visual noise.
* Primary users: internal operators, delivery staff, QA reviewers, and admins.

## Design Principles

1. **Exception-first hierarchy**
   Surface failed jobs, stale jobs, pending QA, and blocked items before generic metrics.

2. **Dense but readable**
   Prefer compact command bars, tables, chips, and state rows over large hero blocks and oversized cards.

3. **Actions stay close to context**
   Queue items should apply filters directly. Row actions should expose one or two primary actions and move low-frequency actions into a menu.

4. **Batch work is a first-class workflow**
   Multi-select and bulk actions should remain available while scrolling through long lists.

5. **Light mode is the primary operating surface**
   Dark mode remains supported and readable, but first-pass visual polish targets light mode.

6. **No decorative complexity**
   Avoid large gradients, glass effects, ornate background patterns, oversized shadows, and illustration-heavy empty states.

## Visual System

### Color

Keep the current indigo/emerald brand memory, but use color more sparingly.

* Primary: indigo for selected states, active navigation, and primary actions.
* Emerald: success, completed states, and positive progress.
* Amber: warnings, stale jobs, pending attention, and non-destructive cautions.
* Rose/red: failures, destructive actions, and blocking errors.
* Slate-like neutrals: page background, table surfaces, borders, labels, and secondary text.

Do not use broad multi-stop gradients as the default surface. Gradients should be limited to small accents, status rails, or primary action emphasis.

### Typography

Retain the existing sans-serif stack unless a later implementation task explicitly changes font loading. The immediate quality gain should come from hierarchy, spacing, and density rather than introducing new font dependencies.

### Surfaces

* Page background: quiet and low contrast.
* Panels: mostly flat or lightly elevated.
* Borders: visible enough to separate dense regions.
* Shadows: shallow, used for sticky bars, popovers, and drawers only.
* Radius: keep the existing 4-10px family; avoid pill-shaped containers except chips and status pills.

### Motion

Use short, stable transitions for hover, focus, row highlight, drawer entry, and sticky action bar reveal. Avoid scale transforms that shift layout.

## Page Patterns

### Compact Command Header

Replaces large hero sections on high-frequency pages.

Required content:

* Page title.
* Short operational description if useful.
* Sync or refresh status.
* Primary page action.
* Refresh/retry action.

Avoid large marketing copy, oversized icons, and decorative workflow strips on dense pages.

### Work Queue Strip

This is the primary first-screen action surface.

Queue items:

* Failed jobs.
* Stale or long-running jobs.
* Pending QA.
* Blocked QA or blocked delivery items.

Each item should include:

* Count.
* Short label.
* Severity or priority signal.
* One click/tap behavior that applies the relevant filter.

### Filters

Use a two-tier filter model:

* Always visible: search, status, QA status, quick exception filters, refresh.
* Advanced popover or drawer: sort, created time range, archived visibility, lower-frequency controls.

Active filters should render as removable chips below the primary filter row.

### Data Table

Use a main-column-first table architecture.

* Main column: file name, job id, mode, and failure summary when applicable.
* Status column: status badge and current stage.
* QA column: QA state and review urgency.
* Progress column: compact progress indicator.
* Time column: updated time first; created time can move to tooltip/detail.
* Actions column: one or two primary actions plus a more-actions menu.

Mobile can use horizontal table scrolling in the first pass. A full card-list mobile layout is out of scope.

### Sticky Bulk Action Bar

When rows are selected, show a bottom sticky action bar.

Required content:

* Selected count.
* Actionable subgroup counts, such as retryable, cancelable, archivable.
* Primary batch actions.
* Clear selection action.

The bar must not hide pagination or destructive confirmation dialogs.

### QA Inbox

The QA queue should move toward an inbox model.

First pass:

* Inbox-style work queue summary.
* Compact queue table.
* Clear "enter QA" or "review" primary action.
* Structural placeholder for a future right-side processing drawer.

Target interaction:

* Right-side drawer for original/translated segment review, term hits, issue type, and action buttons.
* Process one item, then move to the next pending item.

## Global Layout Target

The long-term target is a left compact sidebar plus a top status bar.

This should not block the first page-level redesign. Treat global navigation redesign as a follow-up phase because it touches protected layout, permission-based navigation, responsive behavior, and every page's usable width.

## Empty And Error States

Empty and error states should be actionable:

* No jobs: primary action to create a job.
* Filter returns no jobs: primary action to clear filters.
* Load failure: retry action plus diagnostic context.
* QA queue empty: show the queue is clear and offer "view all" or "view processed".

Avoid large illustrations and broad decorative empty panels.

## Accessibility And Responsiveness

* Preserve visible focus states.
* Use semantic buttons/links for interactive elements.
* Do not rely only on color to indicate failure, warning, success, or selected states.
* Respect reduced motion.
* Verify at 1440px and 375px.
* Desktop is the primary target; mobile only needs to remain usable in the first pass.

## External Design Research Notes

`ui-ux-pro-max` returned "Data-Dense Dashboard" as the most relevant style for this product category. It also highlighted table handling, bulk actions, loading feedback, confirmation feedback, and destructive-action confirmation as relevant UX checks. The generated marketing/table pattern from the broader query is not adopted because md2word is an internal operations workbench, not a conversion landing page.

## First-Pass Anti-Patterns

* Large hero sections on operational list pages.
* KPI cards that push the table below the fold without providing direct action.
* All row actions expanded inline.
* Hiding batch actions once the user scrolls.
* Decorative gradients and glass panels competing with table content.
* Full mobile card redesign before desktop workflows are validated.
