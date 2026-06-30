# P0 Core List Workbench Template Unification Design

## Architecture

This task defines the shared template contract for the three primary queue/workbench pages:

- Jobs,
- Incident Triage,
- Translation QA.

It should establish a common page skeleton while preserving page-specific differences in actions, summaries, and right-side companion surfaces.

## Shared Template Contract

The shared template should define these zones:

1. command header
2. summary strip or inbox strip
3. saved-view strip
4. primary filter zone
5. secondary filter/active-chip zone
6. table or queue body
7. page-level inline result/state zone
8. batch-action or companion action zone

Each page may vary inside the zones, but should not redefine the zones themselves without a documented exception.

## Reuse Boundary

The task should preserve and standardize existing reusable primitives:

- `SavedViewStrip`
- `WorkbenchTableSettings`
- bulk-action bars
- inline result alerts / batch-result strips
- summary chips / quick filters

The task should not assume all pages collapse into one generic component. A shared layout contract is enough for planning.

## Exception Matrix

Known justified differences should remain allowed:

- Jobs has heavy batch actions and richer inline status alerts.
- Incident Triage has a stronger triage summary and direct diagnostic drawer affordances.
- Translation QA uses a queue table plus a processing rail and review drawer flow.

The planning output should document these differences as permitted variants, not regressions.

## State Model

The template should define required state handling for:

- loading,
- empty,
- error,
- permission/no access,
- stale/attention states,
- batch-result feedback.

These are workbench invariants and should not be reinvented per page later.

## Responsive Strategy

The list-workbench template should specify:

- filter wrapping behavior,
- popover/panel visibility constraints,
- table overflow strategy,
- bulk-action placement on small screens,
- preserved access to saved views and table settings on mobile/tablet.

## Dependency Notes

- Depends on shell/token decisions for spacing, density, and color semantics.
- Feeds the accessibility/regression gate with concrete state and responsive requirements.
- Should stabilize before long-tail list/table pages are converged.

## Rollback

Rollback is artifact-only:

- revise the shared-zone contract,
- narrow or expand permitted page exceptions,
- or delay convergence if review finds the pages are still too different for a single template phase.
