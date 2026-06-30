# P1 governance and configuration workbench template

## Goal

Plan a shared governance/configuration page template for settings home, term proposals, translation term sets, and related admin governance surfaces.

## Background

- Governance/configuration pages already exist, but they mix summary, review, diff, form, and publish-risk content with page-specific composition rules.
- These pages should feel like one governed system without collapsing into generic CRUD.
- This child task should define how blockers, drafts, reviews, diffs, and controlled actions are expressed consistently.

## Confirmed Facts

- `frontend/src/pages/SettingsHomePage.vue` already acts as a governance landing page with release gates and grouped findings.
- `frontend/src/pages/TermProposalsPage.vue` combines queue, creation flows, review, and context summaries.
- `frontend/src/pages/TranslationTermSetPage.vue` already exposes draft summary, validation findings, diff/preflight, and compatibility review.
- `frontend/src/pages/WordPageStyleDetailPage.vue` already behaves like a specialized admin workbench with categories, group tabs, and change summary panels.
- The repository already has dialog scroll guard coverage on at least one governance-heavy surface, which should inform shared modal/drawer rules.

## Requirements

- Define a governance-page template for release gates, review queues, draft summaries, diff evidence, and publish blockers.
- Keep complex domain pages readable without collapsing them into generic CRUD forms.
- Standardize severity semantics for blocked, warning, draft, review-needed, and publish-ready states.
- Preserve long-form evidence panels, structured diff zones, and action safety messaging.

## Acceptance Criteria

- [ ] Governance pages define consistent placement for summary metrics, blocker/warning panels, action rails, and evidence tables.
- [ ] Long forms, dialogs, and side panels must keep primary actions reachable while body content scrolls independently.
- [ ] Governance severity labels and visuals are consistent across settings and terminology pages.
- [ ] The template supports both read-mostly governance surfaces and mixed read/write admin surfaces.
- [ ] The PRD documents where domain-specific exceptions are allowed.

## Out Of Scope

- Long-tail low-frequency pages whose main work is alignment rather than governance-specific layout.
- Core queue templates and shell/token decisions.
- Backend governance logic changes or publish-contract changes.

## Notes

- Keep `prd.md` focused on requirements, constraints, and acceptance criteria.
- Lightweight tasks can remain PRD-only.
- For complex tasks, add `design.md` for technical design and `implement.md` for execution planning before `task.py start`.
