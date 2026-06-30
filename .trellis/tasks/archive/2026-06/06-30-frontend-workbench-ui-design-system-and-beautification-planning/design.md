# Frontend Workbench UI Design System And Beautification Planning Design

## Architecture

This parent task is a planning coordinator, not a direct implementation target.

It owns:

1. the cross-page design-system direction,
2. the page-family decomposition,
3. the invariants that every child task must preserve,
4. the sequence in which child tasks should be refined and later executed.

Implementation should happen in child tasks, not in the parent task, unless a later review identifies direct parent-owned integration work that cannot be scoped cleanly to one child.

## Planning Boundaries

The parent task must not become a second source of truth for page-level implementation details.

- Child tasks own detailed page-family requirements and acceptance criteria.
- The parent task owns only shared decisions:
  - design-system direction,
  - `form-table` evaluation framing,
  - page priority ordering,
  - rollout sequencing,
  - accessibility and regression gates that apply everywhere.

This prevents two failure modes:

1. page-level planning duplicated between parent and child artifacts;
2. premature implementation pressure before the design-system rules are stable.

## Existing Frontend Invariant

The audited frontend already has a reusable workbench skeleton:

- protected app shell,
- sidebar/topbar navigation,
- saved views,
- table preferences,
- command palette,
- batch-result strips,
- drawer-based diagnostics,
- responsive smoke coverage on critical flows.

The design direction should therefore be evolutionary, not replacement-driven.

The parent task must preserve this invariant:

```text
existing workbench primitives
  -> become standardized design-system building blocks
  -> child tasks normalize page composition around them
  -> later implementation reuses proven behavior instead of replacing it
```

## Design-System Decision Frame

The target experience is a calm enterprise operations workbench:

- professional rather than promotional,
- data-dense rather than spacious-for-show,
- accessible rather than visually clever,
- evidence-forward rather than chart-first,
- modular rather than page-specific.

The shared design-system decisions that the child tasks must inherit are:

- shell and layout tokens,
- typography hierarchy,
- severity and state semantics,
- evidence surface vocabulary,
- density modes,
- focus/layer behavior,
- responsive guardrails.

These decisions should be refined in the shell/token child and then referenced by the other children.

## `form-table` Decision Boundary

`form-table` is evaluated as a pattern library, not assumed as an integration target.

The parent planning task should enforce the following triage model:

1. Borrow directly
   - configuration-driven list/filter mental models,
   - promise-init loading patterns for detail/edit,
   - column/schema thinking,
   - limited chart linkage ideas.

2. Evaluate wrapper cost first
   - table engines,
   - generic form/detail/edit components,
   - any schema layer that overlaps with saved views, routing, permission behavior, or existing typed APIs.

3. Not suitable
   - dependency-heavy adoption paths,
   - URL/callback data-loading conventions that bypass the current frontend API layer,
   - generic CRUD abstractions over domain-dense diagnostic pages.

This keeps design inspiration separate from dependency commitment.

## Child Task Topology

The planning tree is intentionally split by reusable UI concern, not by file ownership.

```text
Parent: design-system and rollout planning
  -> P0 shell/tokens
  -> P0 core list workbenches
  -> P0 task detail/diagnostics
  -> P0 accessibility/responsive gate
  -> P1 dashboards/system workbenches
  -> P1 governance/configuration workbenches
  -> P2 long-tail admin convergence
```

### Why This Topology

- Shell/tokens must stabilize before page-family visual convergence.
- Core workbenches and detail diagnostics are the highest-frequency operator flows and should shape the core system.
- Accessibility/responsive gates must be planning-complete before visual implementation scales.
- Dashboard/system and governance pages depend on the shared visual language but can plan slightly later.
- Long-tail pages should converge only after the primary patterns prove stable.

## Rollout Strategy

The intended rollout is staged:

1. define shared visual and interaction primitives,
2. normalize highest-frequency workbenches,
3. normalize evidence-heavy detail surfaces,
4. apply the system to dashboard and governance families,
5. converge long-tail admin pages.

This reduces churn and avoids redesigning low-frequency pages against unstable foundations.

## Compatibility And Migration Notes

- The current frontend stack remains Vue + Element Plus.
- Existing tests, smoke coverage, and route/query behaviors must remain valid inputs to later implementation.
- No new dependency or component-library adoption is justified solely by planning artifacts.
- Any future migration to a third-party abstraction must prove compatibility with:
  - current API typing,
  - saved views,
  - route-driven filter restoration,
  - table settings,
  - accessibility behavior,
  - current smoke coverage philosophy.

## Operational Considerations

- Parent-task planning is review-ready only when the child-task map, ordering, and invariants are explicit.
- The parent task should normally remain in planning while child tasks are refined.
- Starting implementation from the parent task would be a smell unless the work truly crosses children and cannot be isolated.

## Rollback

Rollback for this task is planning-only:

- revert the parent PRD/design/implement artifacts,
- keep child tasks if the decomposition is still useful,
- or archive the planning tree if the redesign direction is abandoned.

No application code, dependency, backend contract, or runtime migration is affected by this parent planning artifact.
