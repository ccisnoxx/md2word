# P0 Accessibility And Responsive Regression Gate Design

## Architecture

This task defines the shared non-functional acceptance gate for all redesign implementation.

It should not invent a separate accessibility program. It should convert already-visible project concerns into explicit design and validation requirements.

## Gate Categories

The gate should cover:

1. viewport and overflow rules
2. keyboard access rules
3. focus visibility and return rules
4. overlay/layer rules
5. async/state completeness rules
6. minimum automated validation expectations

## Responsive Contract

The minimum viewport contract should include:

- mobile `375px`
- tablet `768px`
- laptop `1024px`
- desktop `1440px`

The contract should specify that “responsive” does not require feature parity in layout, but does require:

- no horizontal overflow,
- preserved access to primary actions,
- reachable dialogs/drawers/popovers,
- non-obscured filters and command surfaces.

## Accessibility Contract

The task should convert current good practices into required gates:

- visible focus indicators,
- logical tab order,
- keyboard closure for overlays,
- focus return after closing overlays,
- skip-link requirement for nav-heavy shell pages,
- ARIA labeling for custom or non-obvious interactive surfaces.

## State Completeness Contract

Later implementation should not ship visually polished screens that lack core operational states.

The gate should require explicit handling for:

- loading,
- empty,
- error,
- permission/no access,
- warning/attention when applicable.

## Validation Philosophy

The project already uses smoke validation where it matters. The redesign should extend this philosophy:

- use the smallest reliable automated checks,
- prefer overflow/focus/viewport assertions where they exist,
- add targeted checks for newly critical overlay or state behavior,
- avoid broad mandatory full-suite execution unless the touched scope justifies it.

## Rollback

Rollback is planning-only:

- relax or refine gate language,
- change required viewport coverage,
- or narrow the scope if implementation feedback shows some checks belong in page-family tasks instead.
