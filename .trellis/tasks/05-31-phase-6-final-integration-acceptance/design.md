---
doc_type: design
task: 05-31-phase-6-final-integration-acceptance
status: approved
parent: 05-31-project-directory-restructure
---

# Phase 6 design

## Intent

Phase 6 is the final integration acceptance pass for the directory restructure.
It does not introduce another structural migration. Instead, it verifies that
the code and current project knowledge now agree on the layout produced by
Phases 1-5.

## Acceptance surface

The pass covers four surfaces:

- Active code, tests, and scripts: no imports or path defaults should rely on
  removed central packages or old root locations.
- Current documentation: docs under active guides, API references, runbooks,
  and deploy material should point to the final layout. Archived planning
  documents are allowed to preserve historical paths.
- Trellis specs: backend guidelines should describe the implemented
  domain-first layout, `resources/`, `var/`, and persistence adapters.
- CodeStable architecture: architecture pages should not teach future agents to
  use removed packages or old resource/runtime directories.

## Fix strategy

If the audit finds stale current references, fix them directly in the owning
documentation/spec file. Avoid code movement unless validation exposes an
actual import/runtime break from the previous phases.

No compatibility shims are added for old paths. The final layout remains the
single current source of truth.

## Validation strategy

Use regex audits for removed package/path references first, then run targeted
tests and the release check. If a broad release check fails, inspect whether the
failure is caused by this restructure and fix only local, in-scope issues.
