# P2 long-tail admin page convergence

## Goal

Converge lower-frequency admin/configuration pages onto the finalized workbench design system after P0 and P1 templates stabilize.

## Background

- Not every page needs to define the design system. Some pages only need to inherit it once the core patterns settle.
- The long-tail group should remain downstream so that low-frequency pages do not force premature abstraction decisions.
- This child task should document which pages are convergence targets and what “good enough alignment” means for them.

## Confirmed Facts

- The repository already contains lower-frequency admin/configuration pages such as `AiProviderConfigPage.vue`, `AuditLogPage.vue`, `UserManagementPage.vue`, `TemplateListPage.vue`, `TemplateDetailPage.vue`, `TranslationProfilesPage.vue`, `TerminologyReleasesPage.vue`, and other simpler management surfaces.
- These pages already use some shared primitives like `ApiErrorAlert`, cards, forms, and table shells, but their visual density and structure vary noticeably.
- The current parent planning sequence intentionally places this work after shell, core workbench, dashboard, and governance refinement.
- This task should improve consistency, not reopen feature scope or attempt a broad rewrite of already-complex P0/P1 pages.

## Requirements

- Apply the stabilized shell, form, table, and evidence conventions to lower-frequency admin pages.
- Avoid premature redesign of long-tail pages before the core workbench and governance patterns are proven.
- Keep scope limited to convergence and cleanup, not feature expansion.
- Ensure simple admin pages no longer feel visually disconnected from the main workbench.

## Acceptance Criteria

- [ ] Long-tail pages are explicitly downstream of stabilized P0/P1 templates.
- [ ] Simple admin pages define consistent header, panel, form, and description layouts.
- [ ] Empty, error, and permission states converge with the design system instead of remaining ad hoc.
- [ ] Scope excludes new business features unrelated to UI convergence.
- [ ] The PRD identifies the expected dependency on earlier design-system decisions.

## Out Of Scope

- Establishing first-generation design-system primitives.
- Replanning P0 core workbench flows or P1 dashboard/governance layouts.
- New backend/admin features unrelated to UI convergence.

## Notes

- Keep `prd.md` focused on requirements, constraints, and acceptance criteria.
- Lightweight tasks can remain PRD-only.
- For complex tasks, add `design.md` for technical design and `implement.md` for execution planning before `task.py start`.
