# P2 Long-Tail Admin Page Convergence Design

## Architecture

This task is a downstream convergence wave.

It should not invent first-generation patterns. It should apply already-approved shell, list, dashboard, governance, and accessibility conventions to lower-frequency pages.

## Target Surface Set

Likely convergence targets include:

- AI Provider Config,
- Audit Log,
- User Management,
- Template List / Template Detail,
- Translation Profiles,
- Terminology Releases,
- similar lower-frequency management pages.

The exact set may be refined later, but the family is defined by low frequency and limited need to establish new patterns.

## Convergence Model

The task should document what “converged” means:

- shared header treatment,
- shared panel and table rhythm,
- aligned form and descriptions layout,
- consistent empty/error/permission states,
- visual alignment with the main workbench rather than page-specific reinvention.

This is not a mandate to rebuild every page into the same structure.

## Dependency Model

This task explicitly depends on earlier child outputs:

- shell/token rules,
- core list workbench rules where applicable,
- dashboard/governance surface vocabulary,
- accessibility/regression gates.

Without these foundations, long-tail convergence would create unstable abstractions.

## Scope Discipline

The design output should protect against scope drift:

- no new backend/admin feature work,
- no reopening first-generation design-system decisions,
- no broad cleanup unrelated to visible convergence.

## Rollback

Rollback is planning-only:

- narrow the page list,
- postpone some pages to later waves,
- or redefine “convergence” to focus only on shared states and surface treatment.
