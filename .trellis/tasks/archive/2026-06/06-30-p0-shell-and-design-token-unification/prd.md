# P0 shell and design token unification

## Goal

Unify app shell, layout tokens, typography, color roles, and foundational interaction states for the internal operations portal without entering implementation yet.

## Background

- The current frontend already has a protected shell, mobile drawer, topbar, breadcrumb, command palette, and a visually rich login page.
- The current visual language is partially centralized in `frontend/src/styles/main.scss`, but shell and page-family decisions are not yet governed as a formal design system.
- This child task is the first refinement step because all other page-template work depends on stable shell, token, and layering rules.

## Confirmed Facts

- `frontend/src/styles/main.scss` already defines global color, spacing, radius, shadow, motion, and Element Plus bridge variables.
- `frontend/src/layouts/AppLayout.vue` owns the protected shell, topbar, sidebar, mobile drawer, and password dialog behavior.
- `frontend/src/components/AppSidebar.vue` already has a strong navigation identity and collapse/mobile behaviors worth preserving.
- `frontend/src/pages/LoginPage.vue` already establishes a branded entry experience and should be aligned with the protected shell instead of redesigned independently.
- The current visual palette leans indigo/purple, which does not fully match the target “professional, calm, enterprise dashboard” direction.
- The codebase already uses `focus-visible` styling and ARIA labeling widely, but a shared skip-link requirement is not yet captured in planning.
- The app already supports `light` / `dark` / `system` theme modes through `AppThemeToggle.vue` and `data-theme` root switching.
- Current shell behavior is already covered by responsive smoke assertions in `frontend/tests/smoke/core-flow.spec.ts`, including login, shell drawer, collapsed sidebar, and no-horizontal-overflow expectations.

## Requirements

- Define the target token system for color, typography, spacing, radius, shadow, motion, and z-index, using the existing `--app-*` namespace as the primary source of truth.
- Align the app shell experience across login, sidebar, topbar, breadcrumb, main content shell, mobile drawer, and theme toggle.
- Reduce the current SaaS-purple bias in favor of a calmer enterprise operations palette while preserving status semantics and dark-mode parity.
- Preserve the existing command palette, saved-view, and workbench identity instead of replacing it with a generic admin template.
- Decide the shell-level visual and interaction contract now, so later child tasks can reference stable shell rules instead of reopening them.

## Acceptance Criteria

- [ ] The task records a concrete token ownership boundary: global tokens live in `frontend/src/styles/main.scss`, shell composition in `AppLayout.vue`, navigation identity in `AppSidebar.vue`, theme switching in `AppThemeToggle.vue`, and login entry styling in `LoginPage.vue`.
- [ ] The task records a concrete typography decision: headings use `Lexend, "PingFang SC", "Noto Sans SC", sans-serif`; body text uses `"Source Sans 3", "PingFang SC", "Noto Sans SC", sans-serif`; technical text uses `"IBM Plex Mono", "SFMono-Regular", Consolas, monospace`.
- [ ] The task records a concrete light-theme shell palette direction: `--app-color-primary` shifts to a trust blue family, page/body text shifts to slate/navy, and purple-only accents are removed from primary work surfaces.
- [ ] The task records a concrete z-index scale for later implementation: content `1`, sticky topbar `20`, sidebar rail `30`, drawer `40`, popover/dropdown `50`, dialog `60`, command palette `70`, toast/message `80`.
- [ ] Login and protected shell layouts are required to remain usable and overflow-free at `375/768/1024/1440px`, matching the current smoke-test contract.
- [ ] Skip-link, focus-return, visible focus, and keyboard-open/close requirements for shell overlays are explicit enough to be turned into later implementation and smoke checks.
- [ ] The planning artifacts are specific enough that this child task can enter `task.py start` without reopening shell direction decisions.

## Out Of Scope

- Page-family composition for Jobs, Incident Triage, Translation QA, dashboards, or governance pages.
- Replacing the current navigation IA or permission model.
- Introducing new frontend dependencies or implementing the token changes in code during this planning step.
- Replacing light/dark/system theme capability with a single-mode shell.

## Resolved Decisions

- Keep the existing `--app-*` token namespace and evolve values/semantics in place instead of introducing a second parallel token system.
- Keep theme-mode support (`system/light/dark`) in scope; shell/token work must preserve it.
- Prefer a local-first typography strategy for MVP shell implementation. If webfonts are later introduced, they must remain optional and not block the initial shell refresh.
- Preserve the current shell information architecture and command-palette behavior; this task only changes visual and interaction-system consistency.

## Notes

- Keep `prd.md` focused on requirements, constraints, and acceptance criteria.
- Lightweight tasks can remain PRD-only.
- For complex tasks, add `design.md` for technical design and `implement.md` for execution planning before `task.py start`.
