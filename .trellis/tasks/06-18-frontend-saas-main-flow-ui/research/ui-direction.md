# UI Direction Research

## Question

How should the first-round SaaS UI polish be constrained so md2word's main document job flow feels like one mature product without replacing Element Plus or changing behavior?

## Findings

- The user explicitly requested a Stripe / Linear style direction: refined, restrained, professional, and clearly layered.
- The local `ui-ux-pro-max` design-system search for document conversion SaaS returned a vibrant/immersive direction by default. That conflicts with the requested direction and should not be adopted for this task.
- More relevant local design search results point toward Swiss/minimal SaaS conventions:
  - strict grid and spacing system
  - high readability and clear hierarchy
  - neutral surfaces with a single restrained primary accent
  - minimal decoration and subtle hover/focus states
  - responsive table handling and stable layout dimensions
- Existing project code already uses Element Plus, Vue 3, scoped SCSS, and a small global `main.scss`. The lowest-risk approach is to expand the project's own SCSS token layer and converge existing page/component styles onto it.

## Repo Constraints

- Do not introduce a new UI library or replace Element Plus.
- Keep routing, permissions, upload flow, polling, task actions, API payloads, and error behavior unchanged.
- Main flow files are already business-rich; the UI task should avoid broad component abstraction unless it removes real style duplication.
- Project currently has no frontend-specific Trellis spec. Implementation should use inspected frontend files and the PRD as the authoritative local convention.

## Recommended Approach

Use "project tokens + main-flow CSS templates + scoped component cleanup":

- Put semantic design tokens in `frontend/src/styles/main.scss`.
- Reuse those tokens from `AppLayout`, `/jobs`, `/jobs/new`, `/jobs/:id`, and shared job components.
- Keep Element Plus components and customize their shell through SCSS only where needed.
- Prefer consistent page/header/panel/toolbar/table/form/status classes over new Vue layout abstractions in this first round.

## Risks To Check

- Hidden behavior regression from accidentally changing button disabled/loading conditions.
- Mobile table overflow or cramped action buttons.
- Token definitions that become a second source of truth if page-specific variables remain duplicated.
- Over-styling deep Element Plus selectors in a way that affects out-of-scope pages.
