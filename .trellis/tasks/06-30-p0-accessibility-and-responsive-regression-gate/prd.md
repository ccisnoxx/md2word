# P0 accessibility and responsive regression gate

## Goal

Define cross-page accessibility, responsive, focus-management, and regression validation gates for the workbench redesign rollout.

## Background

- The current frontend already has better-than-average smoke coverage for overflow and some interactive surfaces, but the rules are not centralized as planning gates.
- Accessibility and responsive requirements should be treated as explicit contract work, not cleanup after visual implementation.
- This child task should provide the shared non-functional gate for all later redesign execution.

## Confirmed Facts

- Existing smoke tests already check no-horizontal-overflow behavior on multiple pages and dialogs at `375`, `768`, and desktop sizes.
- The frontend already uses `focus-visible` styling and many `aria-label` / `aria-labelledby` attributes.
- Dialogs, drawers, popovers, and command-palette-like overlays already exist and therefore need a shared z-index and focus-return contract.
- A project-wide skip-link pattern is not yet implemented or captured in task planning.
- Core pages already use loading skeletons, empty states, and error alerts, but permission-state handling is not yet framed as a universal gate.

## Requirements

- Establish viewport and overflow rules that every redesigned page must satisfy.
- Capture keyboard navigation, focus visibility, skip-link, dialog/drawer, and z-index expectations as explicit gates.
- Reuse and extend the current smoke-testing mindset instead of relying on manual visual checks alone.
- Keep validation scoped to the smallest reliable set of build, unit, and smoke checks for each rollout stage.

## Acceptance Criteria

- [ ] Target pages define no-horizontal-overflow expectations for `375/768/1024/1440px`.
- [ ] Dialogs, drawers, popovers, and the command palette have explicit focus and layering requirements.
- [ ] Core pages define mandatory `loading/empty/error/permission` state coverage.
- [ ] The task records which automated checks are expected before later implementation closes.
- [ ] Accessibility gates are phrased as testable outcomes, not only design aspirations.

## Out Of Scope

- Inventing a new testing stack unrelated to the current Vitest/Playwright setup.
- Replanning page-family visual structure already owned by other child tasks.
- Backend, auth, or permission-model changes.

## Notes

- Keep `prd.md` focused on requirements, constraints, and acceptance criteria.
- Lightweight tasks can remain PRD-only.
- For complex tasks, add `design.md` for technical design and `implement.md` for execution planning before `task.py start`.
