---
doc_type: design
task: 05-31-phase-4-remaining-domain-migrations
status: approved
parent: 05-31-project-directory-restructure
---

# Phase 4 design

## Intent

Phase 4 applies the domain-first package pattern proven by `app/domains/files/`
to the remaining backend domains. This is still a behavior-preserving directory
and import migration: services, models, schemas, routers, and repository ports
move to owning packages; HTTP contracts, persistence formats, worker behavior,
and conversion behavior stay stable.

## Target domain packages

```text
app/domains/
├── audit/
├── document_jobs/
├── files/
├── jobs/
├── resources/
├── templates/
├── term_rules/
└── translation/
```

Each package uses the same simple shape where applicable:

```text
app/domains/<domain>/
├── __init__.py
├── models.py
├── repository.py
├── router.py
├── schemas.py
└── service modules
```

Large domains may keep multiple service or router modules beside the
resource-level `router.py` aggregator. This preserves the existing split for
`jobs` and the separate write/category/set routes for `term_rules`.

## Domain ownership

- `audit`
  - moves `app/core/audit_models.py`
  - moves `app/services/audit.py`
  - owns `AuditEventRepositoryProtocol`
- `resources`
  - moves `app/core/resource_models.py`
  - moves `app/services/resource_versions/`
  - owns `ResourceVersionRepositoryProtocol`
- `translation`
  - moves `app/core/translation_models.py`
  - moves `app/services/translation/`
  - moves `app/services/translation_profiles/`
  - moves `app/services/terms/term_version_service.py`
  - moves `app/schemas/translation_profiles.py`
  - moves `app/api/v1/routers/translation_profiles.py`
- `document_jobs`
  - moves `app/core/document_job_models.py`
  - moves `app/schemas/document_jobs.py`
  - moves `app/services/document_jobs/`
  - moves `app/api/v1/routers/document_jobs.py`
  - owns document job repository ports
- `templates`
  - moves `app/core/template_models.py`
  - moves `app/schemas/templates.py`
  - moves `app/services/templates/read_service.py`
  - moves `app/api/v1/routers/templates.py`
- `term_rules`
  - moves `app/core/rule_models.py`
  - moves `app/schemas/term_rules.py`
  - moves `app/services/term_rules/`
  - moves `app/api/v1/routers/term_rules.py`
  - moves `app/api/v1/routers/term_rule_sets.py`
  - moves `app/api/v1/routers/term_rule_categories.py`
  - moves `app/api/v1/routers/term_rule_write_guard.py`
  - moves `app/repositories/file_term_rule_repository.py`
  - owns `TermRuleRepositoryProtocol`
- `jobs`
  - moves `app/core/job_models.py`
  - moves `app/core/job_paths.py`
  - moves `app/core/job_workflow.py`
  - moves `app/core/mineru_callback.py`
  - moves `app/schemas/jobs.py`
  - moves `app/services/jobs/`
  - moves `app/api/v1/routers/jobs*.py`
  - moves `app/api/v1/routers/mineru_callbacks.py`
  - owns job, file, event, and stage-message repository ports

## Boundaries that stay put

- `app/api/dependencies.py`, `app/api/errors.py`, and
  `app/api/mineru_callback_guards.py` remain API composition/helpers.
- `app/infrastructure/persistence/` remains the concrete adapter layer.
- `app/conversion/`, `app/workers/`, `app/clients/`, auth, health,
  document-IR, and renderer code are not Phase 4 migration targets except for
  import updates.
- `app/schemas/` and `app/services/` may remain as smaller packages after this
  task. Removing obsolete package shells belongs to Phase 5.

## Compatibility strategy

No old-path re-export modules are added. Imports in active code, tests, and
scripts are updated to the new domain packages. Existing module headers are
updated after each move.

OpenAPI should remain behaviorally stable. Any generated difference must be
reviewed before accepting the migration.

## Validation strategy

Each domain gets a targeted compile/import check and the smallest relevant unit
tests before the next domain. A final stale-import audit checks `app`, `tests`,
and `scripts`; historical docs may still contain old paths.
