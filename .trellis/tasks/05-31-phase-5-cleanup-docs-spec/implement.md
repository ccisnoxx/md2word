---
doc_type: implement-plan
task: 05-31-phase-5-cleanup-docs-spec
status: approved
parent: 05-31-project-directory-restructure
---

# Phase 5 implementation plan

## Step 0: Confirm cleanup surface

Commands:

```bash
git status --short
rg "app\\.schemas|app\\.repositories" app tests scripts
rg "app\\.core\\.(audit_models|resource_models|translation_models|document_job_models|template_models|rule_models|job_models|job_paths|job_workflow|mineru_callback|file_models)" app tests scripts
```

Expected:

- only auth/health schemas and transition tests still reference `app.schemas`
- no active old domain model imports remain

## Step 1: Remove schema and repository transition modules

Actions:

- Add `app/api/v1/schemas.py` for auth and health v1 API models.
- Update auth/health routers and health service imports.
- Update tests to use direct domain/API schema imports instead of
  `app.schemas.api_v1`.
- Delete `app/schemas/*` and `app/repositories/*` source modules.
- Remove stale `__pycache__` directories from old moved packages.

Checks:

```bash
rg "app\\.schemas|app\\.repositories" app tests scripts
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_health_ready_reports_runtime_dependencies
```

## Step 2: Update Trellis directory spec

Actions:

- Rewrite `.trellis/spec/backend/directory-structure.md` around the final
  domain-first backend layout.
- Keep placement rules explicit for domains, persistence, API-only auth/health
  schemas, `resources/`, `var/`, and `scripts/dev/`.

Checks:

```bash
rg "app/schemas|app/repositories|app/services/jobs|app/core/job_models|data/" .trellis/spec/backend/directory-structure.md
```

## Step 3: Update CodeStable architecture

Actions:

- Update `.codestable/architecture/ARCHITECTURE.md`.
- Update `.codestable/architecture/backend-fastapi-service.md`.
- Update conversion architecture pages that still mention old
  `prompt/` or `template_configs/` paths.

Checks:

```bash
rg "app/schemas|app/repositories|app/services/(jobs|templates|term_rules|translation|translation_profiles|resource_versions|document_jobs|audit)|app/core/(job_models|job_paths|resource_models|audit_models|translation_models|template_models|rule_models|document_job_models)|template_configs|template/|prompt/|\\bdata/" .codestable/architecture
```

## Step 4: Update current docs and final verification

Actions:

- Update current API docs/manifest source path lists to domain-owned modules.
- Leave archived planning/history documents untouched unless they are current
  docs by location.

Checks:

```bash
rg "app\\.schemas|app\\.repositories" app tests scripts
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/check_release.py
```

If `check_release.py` is blocked by unrelated local state, record the exact
failure and keep the targeted test result.
