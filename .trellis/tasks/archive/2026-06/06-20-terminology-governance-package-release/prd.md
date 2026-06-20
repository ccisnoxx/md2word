# Terminology Governance Package Release

## Goal

Upgrade the Quality menu and terminology workflow from separate term-set and rule-set management into a governed release flow centered on a terminology governance package. A package publishes a translation term set version, rule configuration version, and an applicability scope together, with preflight validation, conflict scanning, release history, rollback, and proposal handoff.

## Requirements

- Keep Quality as tool-style entries plus lifecycle constraints: Translation QA, Proposal Review, Translation Term Sets, Term Rules, and Term Releases.
- Treat the release object as a governance package composed of term set version, rule set/config version, and scope.
- Scope is `project + language_pair + content_type`; exact duplicate active scope releases are blocked.
- Releases with overlapping scope must run conflict scanning; high-risk conflicts block publish.
- Translation Term Sets own terminology entries and translations, not rules.
- Term entry fields must support source term, recommended translations, forbidden translations, synonyms, language pair, project, content type, tags, status, updated time, and maintainer.
- Term entry status is `editing`, `publishable`, or `deprecated`; only `publishable` entries can enter a governance package.
- Term Rules own checking constraints/templates, not concrete translations.
- Rule templates are grouped into basic rules, format rules, and matching settings.
- Operators cannot create formal term rules. The formal create button must be disabled with an explanation and a shortcut to Proposal Review prefilled as a term rule suggestion.
- Term Release page contains a release list, active scope overview, and a new release wizard.
- Wizard steps: select term set version, select rule configuration, set scope, run preflight, confirm release.
- Hard blocking preflight: duplicate scope, invalid reference, no publishable terms, missing rule configuration.
- High-risk conflicts: recommended translation conflict, forbidden term conflict, mutually exclusive rules.
- Release list supports details, rollback, copy as new release, and validation report.
- Translation QA adds terminology issue display and links to term details or proposal creation.
- Proposal Review supports proposal types: new term, translation update, deprecate term, and term rule suggestion.
- Approved term proposals enter the Translation Term Set flow; rule suggestions become administrator-owned rule drafts.

## Acceptance Criteria

- Quality navigation shows the five terminology/QA entries in the agreed order and routes to the correct pages.
- Operators see Term Rules as read-only; formal creation is disabled with the agreed explanation and proposal shortcut.
- A governance package can be created through API and UI with `term_set + rule_set + scope`.
- Duplicate active scope publish is rejected with a stable API error.
- Invalid references, missing publishable terms, and missing rule config block preflight/publish.
- Conflict findings are persisted in the release validation report and block high-risk publish.
- Release list shows details, rollback, copy-as-new, and validation report affordances.
- New document/job term asset binding can resolve the active governance package by `project + language_pair + content_type` without rewriting existing job snapshots.
- Targeted backend tests and frontend build/tests cover the new contracts.

## Technical Approach

- Add a terminology governance package domain with models, schemas, service, repository protocol, routers, and file/sqlite/mysql adapters.
- Keep existing `translation-term-sets` and `term-rule-sets` as lower-level asset versioning APIs; the new release page consumes both.
- Extend Translation Term Set entries in a backward-compatible way, mapping existing `active` to `publishable` and `disabled` to `deprecated`.
- Add proposal type support for term rule suggestions while preserving existing proposal review queues.
- Update the frontend navigation, Term Rules page permissions, and a new Term Release page with a compact Element Plus workbench layout.

## Out of Scope

- Full multi-tenant project hierarchy beyond the explicit `project` string scope.
- Changing existing completed job snapshots.
- Replacing existing term rule runtime YAML consumption in the conversion path.
- Removing legacy term rule set and translation term set APIs.

## Technical Notes

- Existing relevant frontend files: `frontend/src/navigation/appShell.ts`, `frontend/src/router/index.ts`, `frontend/src/pages/TermRuleWorkbenchPage.vue`, `frontend/src/pages/TranslationTermSetPage.vue`, `frontend/src/pages/TermRuleSetPage.vue`, `frontend/src/pages/TermProposalsPage.vue`.
- Existing relevant backend files: `app/domains/translation/*`, `app/domains/term_rules/*`, `app/domains/jobs/resource_snapshots.py`, `app/domains/document_jobs/config_summary.py`, `app/infrastructure/persistence/*`, `app/main.py`, `app/core/runtime.py`.
- Follow `.trellis/spec/backend/*`, `.trellis/spec/frontend/*`, and shared cross-layer/code-reuse guides.
