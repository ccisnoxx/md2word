# P0 Task Detail And Diagnostic Interaction Template Design

## Architecture

This task defines the evidence-surface contract for:

- the full Job Detail page,
- Incident Triage diagnostic drawers,
- Translation QA review drawers.

The core question is not “what component to use,” but “what reading order and interaction model operators need when the surface is evidence-heavy.”

## Surface Model

The task should define two related but distinct surfaces:

1. primary detail page
2. secondary right-drawer workflow

The primary detail page can hold deeper multi-section evidence. The secondary drawer should optimize for quick triage/review with controlled depth.

## Evidence Reading Order

The shared evidence order should generally be:

1. current state
2. recommended next action
3. critical summary facts
4. supporting evidence
5. technical traces / raw identifiers
6. secondary history or configuration context

Each surface may compress or expand this order, but should not invert it without strong justification.

## Drawer Contract

The drawer pattern should define:

- open/close ownership,
- focus entry and focus return,
- keyboard close behavior,
- compact-screen width constraints,
- safe scroll ownership,
- when to deep-link out to a full detail page.

## Technical Content Contract

Technical content such as IDs, file references, logs, event snippets, and diff-like payloads should be visually distinct from narrative copy.

The planning output should define a shared technical/evidence style for:

- monospace identifiers,
- copy-friendly blocks,
- evidence cards,
- warnings vs blockers,
- structured list vs raw block usage.

## Boundary With Other Tasks

- This task does not own queue-page composition.
- This task depends on shell/token rules for typography and spacing.
- It should inform governance pages where drawer or side-panel evidence patterns overlap.

## Rollback

Rollback is planning-only:

- revise the evidence order,
- narrow the drawer contract,
- or document that some surfaces need stronger specialization than first assumed.
