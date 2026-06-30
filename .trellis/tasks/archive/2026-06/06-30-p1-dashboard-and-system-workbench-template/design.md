# P1 Dashboard And System Workbench Template Design

## Architecture

This task defines the template family for operational dashboards and system-status surfaces:

- Operations Cockpit,
- System Status,
- Ops Dashboard,
- Acceptance Center.

These pages are not interchangeable, but they should share an operational hierarchy and a common set of surface types.

## Template Model

The dashboard/system template should describe:

1. first-screen summary/KPI zone
2. alert and blocker zone
3. operational advice or action zone
4. evidence/detail module zone
5. secondary references/deep links

Not every page needs every zone at the same weight, but the hierarchy should stay recognizable.

## Surface Vocabulary

The family should converge on a reusable set of surface types:

- KPI/metric cards,
- status cards,
- alert stacks,
- evidence panels,
- action safety panels,
- reference-link panels.

This creates consistency without forcing identical layouts.

## Chart Policy

Charts should remain optional and justified.

The planning contract should prefer:

- metric cards for fast state reading,
- alerts for blockers,
- evidence tables/panels for operator trust,
- line/area charts only when time-series interpretation materially helps.

This is important because `OpsDashboard` and `AcceptanceCenter` are safety/evidence surfaces, not BI screens.

## State And Freshness Contract

The family must explicitly handle:

- loading,
- empty,
- error,
- freshness / last updated,
- dry-run or safety-mode semantics where applicable.

This is especially important because these pages often reflect asynchronous backend status snapshots rather than direct CRUD lists.

## Boundary With Other Tasks

- Depends on shell/token decisions for overall visual language.
- Depends on accessibility/regression planning for responsive and overlay expectations.
- Should remain separate from governance/configuration page planning because its information hierarchy is operational, not editorial/governance-first.

## Rollback

Rollback is planning-only:

- simplify the zone model,
- reduce the surface vocabulary,
- or narrow chart guidance if later review finds the family should be even more evidence-first.
