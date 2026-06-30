# Frontend workbench UI design system and beautification planning

## Goal

Create the planning backbone for frontend UI audit, design-system definition, `form-table` borrowing evaluation, page prioritization, and phased workbench beautification across the Vue + Element Plus internal portal.

User value: stop treating the frontend as a set of page-by-page visual fixes. Establish a reusable enterprise workbench language so that the highest-frequency operator flows become calmer, denser, more legible, and easier to validate without rewriting proven business behavior.

## Background

- The current frontend already serves a real internal operations workflow: login, work queues, incident triage, job diagnostics, translation QA, settings governance, system status, and acceptance evidence.
- The repository already contains custom shell and workbench primitives. The problem is not “lack of UI,” but inconsistent page-level composition and insufficient design-system governance.
- The user explicitly asked for a planning-only phase first: audit, design recommendations, `form-table` evaluation, page prioritization, and Trellis task decomposition before any implementation.
- The user explicitly asked not to install `form-table` yet. Any adoption decision must follow planning and wrapper-cost evaluation.

## Confirmed Facts

- The current frontend already has a custom workbench shell, navigation, saved views, table preferences, command palette, batch-result strips, and drawer-based diagnostics.
- The target product type is a B2B internal operations portal for document conversion, QA, and operations dashboards.
- The current phase is planning-only. No implementation code should be written in this task tree.
- `form-table` should be evaluated for borrowing patterns first; it should not be installed yet.
- The current stack is Vue 3 + Element Plus + Pinia + Vue Router, with project-specific global tokens and smoke coverage already present in the frontend package.
- The current workbench has strong repeated patterns across `Jobs`, `Incident Triage`, `Translation QA`, `Job Detail`, `Operations Cockpit`, `Ops Dashboard`, `Settings Home`, and governance/configuration pages.
- Existing smoke tests already protect responsive overflow and key workflow behavior for several core pages; the redesign should extend this validation mindset rather than replace it with subjective manual review.
- `form-table-vue3` brings a useful configuration-driven mental model, but also heavier peer dependencies and callback/data-loading conventions that do not automatically match the current typed API architecture.

## Requirements

### Product And UX Requirements

- R1. Define a target design-system direction for a professional, data-dense, calm, accessible enterprise workbench rather than a marketing-style dashboard or a generic CRUD admin.
- R2. Preserve existing operator workflow strengths: direct queue entry, saved views, dense evidence surfaces, keyboard access, and task/deep-link navigation.
- R3. Improve consistency across shell, list workbenches, detail diagnostics, dashboards, governance/configuration pages, and long-tail admin pages without forcing all pages into one identical layout.
- R4. Keep information hierarchy explicit: critical action, summary, filter context, evidence, and secondary technical detail must be separated visually.

### Architecture And Reuse Requirements

- R5. Treat the existing custom shell/workbench primitives as the primary source of UI direction; do not replace them prematurely with a third-party library abstraction.
- R6. Separate `form-table` conclusions into three buckets:
  1. patterns that can be borrowed directly,
  2. patterns that require wrapper-cost evaluation first,
  3. patterns or dependencies that are not suitable for the current project.
- R7. Any future `form-table` adoption decision must be made after compatibility review with the current typed API layer, routing model, saved-view behavior, table preferences, accessibility constraints, and test strategy.
- R8. The parent planning task must own the cross-child decisions and invariants; child tasks own their specific page families and acceptance gates.

### Planning And Scope Requirements

- R9. Keep P0/P1/P2 prioritization aligned with the audited page families:
  - P0: shell, core list workbenches, task detail/diagnostics, accessibility/regression gate
  - P1: dashboards/system workbenches, governance/configuration templates
  - P2: long-tail admin convergence
- R10. Split planning into independently reviewable child tasks for shell, core workbenches, detail diagnostics, dashboards, governance pages, accessibility gates, and long-tail admin convergence.
- R11. Keep all newly created Trellis tasks in `planning` status until the user explicitly asks to continue planning or implementation.
- R12. The parent task must become review-ready with `prd.md`, `design.md`, and `implement.md` before any child is advanced toward implementation.

## Acceptance Criteria

- [ ] The parent task documents the product goal, confirmed facts, planning boundaries, and cross-child invariants for the UI beautification effort.
- [ ] A parent task exists with child tasks covering the agreed P0/P1/P2 split.
- [ ] Each child task has a non-placeholder goal, scope, and acceptance skeleton in `prd.md`.
- [ ] The task tree reflects planning-only boundaries and does not start implementation.
- [ ] The parent task captures the requirement that `form-table` is evaluated before any installation or adoption decision.
- [ ] The parent task defines how later implementation will be sequenced across child tasks instead of allowing uncoordinated page-by-page redesign.
- [ ] The user can continue planning from this task tree without reconstructing the audit context.

## Child Task Map

- `06-30-p0-shell-and-design-token-unification`
  - Owns shell, token, typography, spacing, color, depth, and layer-system planning.
- `06-30-p0-core-list-workbench-template-unification`
  - Owns shared list workbench structure across Jobs, Incident Triage, and Translation QA.
- `06-30-p0-task-detail-and-diagnostic-interaction-template`
  - Owns task detail, diagnostic summary, drawer behavior, and evidence presentation planning.
- `06-30-p1-dashboard-and-system-workbench-template`
  - Owns cockpit/system/dashboard/acceptance information hierarchy planning.
- `06-30-p1-governance-and-configuration-workbench-template`
  - Owns governance/configuration page template planning.
- `06-30-p0-accessibility-and-responsive-regression-gate`
  - Owns responsive and accessibility regression gates shared by all redesign work.
- `06-30-p2-long-tail-admin-page-convergence`
  - Owns downstream alignment of lower-frequency admin pages after core templates stabilize.

## Out Of Scope

- No implementation code changes in `frontend/src/` during this parent planning task.
- No `form-table` installation or dependency changes during this parent planning task.
- No visual rewrites outside the agreed task tree.
- No backend contract changes, route changes, or business-logic changes as part of the parent planning artifact work.
- No attempt to flatten all pages into a single universal component or CRUD schema.

## Open Questions

- None blocking at the parent-task level after the current planning decomposition. Remaining decisions should be resolved within child-task planning before implementation.

## Notes

- Keep `prd.md` focused on requirements, constraints, and acceptance criteria.
- Lightweight tasks can remain PRD-only.
- For complex tasks, add `design.md` for technical design and `implement.md` for execution planning before `task.py start`.
