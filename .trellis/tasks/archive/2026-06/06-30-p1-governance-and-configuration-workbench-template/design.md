# P1 Governance And Configuration Workbench Template Design

## Architecture

This task defines the template family for governance/configuration workbenches such as:

- Settings Home,
- Term Proposals,
- Translation Term Sets,
- Word Page Style Detail,
- related admin governance surfaces.

The family is unified by controlled decision-making, blocker/warning semantics, and evidence-backed change workflows.

## Template Model

The governance/configuration family should support these recurring zones:

1. summary and release-gate overview
2. blocker/warning or governance-context zone
3. primary workspace or review queue
4. evidence/diff/compatibility zone
5. controlled action zone

Some pages are read-mostly; others mix edit/review/publish actions. The template should permit both.

## Severity Model

The family should converge on consistent severity semantics for:

- blocked,
- warning,
- review needed,
- draft,
- ready/publishable,
- unavailable.

This is more important than visual novelty because operator/admin judgment depends on severity trust.

## Form And Panel Rules

The task should define:

- long-form behavior,
- scroll ownership for dialogs and side panels,
- preservation of primary actions,
- placement of contextual metadata and evidence references,
- how diff-like or preflight findings should be grouped visually.

## Exception Strategy

Known allowed differences:

- `SettingsHome` is a landing/governance dashboard.
- `TermProposals` mixes creation and review.
- `TranslationTermSet` is evidence- and diff-heavy.
- `WordPageStyleDetail` behaves like a specialized editor/workbench.

The family should therefore share a vocabulary, not a single identical composition.

## Boundary With Other Tasks

- Depends on shell/token decisions for visual baseline.
- Should align with diagnostics and accessibility rules where drawers/dialogs overlap.
- Remains separate from long-tail admin convergence because it still defines first-class patterns.

## Rollback

Rollback is planning-only:

- reduce the family scope,
- refine the severity vocabulary,
- or split specialized editors out if review finds they need a stronger exception path.
