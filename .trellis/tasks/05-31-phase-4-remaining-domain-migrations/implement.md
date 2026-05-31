---
doc_type: implement-plan
task: 05-31-phase-4-remaining-domain-migrations
status: approved
parent: 05-31-project-directory-restructure
---

# Phase 4 implementation plan

## Rules

- Implement domains in this exact order: `audit`, `resources`, `translation`,
  `document_jobs`, `templates`, `term_rules`, `jobs`.
- Preserve behavior and HTTP contracts.
- Do not start Phase 5 cleanup.
- Do not add old-module compatibility shims.
- Keep concrete persistence adapters under `app/infrastructure/persistence/`.
- Use `/Users/sc/miniconda3/envs/md2word/bin/python` for verification.
- Respect existing Phase 1-3 dirty worktree changes.

## Step 0: Baseline

Commands:

```bash
git status --short
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_database_job_repository
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend
```

If a baseline fails due to unrelated local state, continue with the narrower
domain-specific checks and record the failure.

## Step 1: audit

Actions:

- Create `app/domains/audit/`.
- Move audit models and service into the domain.
- Move `AuditEventRepositoryProtocol` into `app/domains/audit/repository.py`.
- Update API dependencies, routers, services, and persistence adapters.

Checks:

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m py_compile app/domains/audit/*.py
rg "app\\.core\\.audit_models|app\\.services\\.audit|AuditEventRepositoryProtocol" app tests scripts
```

## Step 2: resources

Actions:

- Create `app/domains/resources/`.
- Move resource-version models and service into the domain.
- Move `ResourceVersionRepositoryProtocol` into the domain.
- Update persistence adapters, resource snapshot code, templates,
  term-rules, translation-profile services, and tests.

Checks:

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_resource_versioning
rg "app\\.core\\.resource_models|app\\.services\\.resource_versions|ResourceVersionRepositoryProtocol" app tests scripts
```

## Step 3: translation

Actions:

- Create `app/domains/translation/`.
- Move translation models, provider, DocumentIR translation service, AI audit
  service, term-version service, translation-profile schemas/service/router.
- Update conversion, jobs, document_jobs, main runtime wiring, and tests.

Checks:

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_document_ir_translation
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_translation_runtime_characterization
rg "app\\.core\\.translation_models|app\\.services\\.translation|app\\.services\\.translation_profiles|app\\.services\\.terms|app\\.schemas\\.translation_profiles|app\\.api\\.v1\\.routers\\.translation_profiles" app tests scripts
```

## Step 4: document_jobs

Actions:

- Create `app/domains/document_jobs/`.
- Move models, schemas, service, execution queue, router, and repository ports.
- Update workers, translation audit, persistence adapters, runtime wiring, and
  tests.

Checks:

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_database_job_repository
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend
rg "app\\.core\\.document_job_models|app\\.schemas\\.document_jobs|app\\.services\\.document_jobs|app\\.api\\.v1\\.routers\\.document_jobs|DocumentJobRepositoryProtocol|DocumentJobEventRepositoryProtocol" app tests scripts
```

## Step 5: templates

Actions:

- Create `app/domains/templates/`.
- Move template models, schemas, read/versioning service, and router.
- Update document_jobs, jobs resource snapshots, runtime wiring, and tests.

Checks:

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend
rg "app\\.core\\.template_models|app\\.schemas\\.templates|app\\.services\\.templates|app\\.api\\.v1\\.routers\\.templates" app tests scripts
```

## Step 6: term_rules

Actions:

- Create `app/domains/term_rules/`.
- Move term-rule models, schemas, services, routers, write guard, file
  repository, and repository port.
- Update jobs resource snapshots, main runtime wiring, tests, scripts, and
  API router aggregation.

Checks:

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_resource_versioning
rg "app\\.core\\.rule_models|app\\.schemas\\.term_rules|app\\.services\\.term_rules|app\\.repositories\\.file_term_rule_repository|app\\.api\\.v1\\.routers\\.term_rule" app tests scripts
```

## Step 7: jobs

Actions:

- Create `app/domains/jobs/`.
- Move job models, path helpers, workflow rules, MinerU callback helper,
  schemas, services, routers, callback router, presenter helpers, and job
  repository ports.
- Update persistence adapters, API error mapping, workers, conversion,
  scripts, and tests.

Checks:

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_job_workflow_policy
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_job_artifact_contract
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend
rg "app\\.core\\.job_models|app\\.core\\.job_paths|app\\.core\\.job_workflow|app\\.core\\.mineru_callback|app\\.schemas\\.jobs|app\\.services\\.jobs|app\\.api\\.v1\\.routers\\.jobs|app\\.api\\.v1\\.routers\\.mineru_callbacks|JobSnapshotRepositoryProtocol|JobEventRepositoryProtocol|JobFileRepositoryProtocol|StageMessageStoreProtocol" app tests scripts
```

## Step 8: Final verification

Commands:

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_database_job_repository
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_resource_versioning
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_document_ir_translation
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_translation_runtime_characterization
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/export_openapi.py --check
```

Final stale-import audit:

```bash
rg "app\\.core\\.(audit_models|resource_models|translation_models|document_job_models|template_models|rule_models|job_models|job_paths|job_workflow|mineru_callback)|app\\.schemas\\.(translation_profiles|document_jobs|templates|term_rules|jobs)|app\\.services\\.(audit|resource_versions|translation|translation_profiles|terms|document_jobs|templates|term_rules|jobs)|app\\.api\\.v1\\.routers\\.(translation_profiles|document_jobs|templates|term_rules|term_rule_sets|term_rule_categories|term_rule_write_guard|jobs|jobs_ingest|jobs_query|jobs_ops|jobs_presenters|mineru_callbacks)|app\\.repositories\\.file_term_rule_repository" app tests scripts
```

Expected:

- active old-domain imports are gone
- domain routers are included from `app.domains.*`
- targeted tests pass
- no Phase 5 cleanup was performed
