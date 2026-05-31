---
doc_type: implement-plan
task: 05-31-project-directory-restructure
status: draft
---

# Project directory restructure implementation plan

## Execution rules

- Do not start code moves until `prd.md`, `design.md`, and this plan are
  reviewed.
- Use staged implementation. Each phase must compile/import and pass its
  validation before the next phase starts.
- Do not keep compatibility shims for old root paths.
- All nine scan findings remain in the parent scope, but implementation is
  approved one phase at a time. Preparing Phase 1 does not approve Phases 2-5.
- Use the project interpreter for verification:
  `/Users/sc/miniconda3/envs/md2word/bin/python`.
- Avoid unrelated cleanup inside moved files. Directory moves and import fixes
  are enough unless a phase explicitly calls for code restructuring.

## Phase 0: Baseline and guardrails

- Record dirty worktree state before editing, because this repository already
  has unrelated local changes.
- Confirm active task remains `.trellis/tasks/05-31-project-directory-restructure`.
- Re-read `.trellis/spec/backend/directory-structure.md` and update it only
  after the target layout is implemented or at the phase that changes the rule.

Validation:

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_llm_client_characterization
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend
```

Rollback:

- Stop before file moves if baseline tests fail for unrelated reasons; record
  the failure and choose a smaller baseline command.

## Phase 1: Root, resources, runtime, docs, and fixtures

Child task: `.trellis/tasks/05-31-phase-1-root-resources-runtime-layout`.

Steps:

- Create `scripts/dev/` and move local runners:
  - `run_api.py` -> `scripts/dev/run_api.py`
  - `run_worker.py` -> `scripts/dev/run_stage_worker.py`
  - `run_document_worker.py` -> `scripts/dev/run_document_worker.py`
- Move `config.py` -> `app/conversion/runtime_config.py`; update conversion
  imports.
- Create `resources/` and move:
  - `template/datasheet_template.docx` -> `resources/templates/default/datasheet_template.docx`
  - `template_configs/datasheet_template.yaml` -> `resources/template_configs/datasheet_template.yaml`
  - `template_configs/templates_manifest.yaml` -> `resources/template_configs/templates_manifest.yaml`
  - `template_configs/term_rules.v2.yaml` -> `resources/term_rules/term_rules.v2.yaml`
  - `template_configs/translation_terms.csv` -> `resources/term_rules/translation_terms.csv`
  - `template_configs/subscripts_dictionary*.yaml` -> `resources/term_rules/`
  - `prompt/translation_en2zh.md` -> `resources/prompts/translation_en2zh.md`
- Change runtime state default root from `data` to `var`.
- Move test assets:
  - `tests/golden_samples/` -> `tests/fixtures/golden_samples/`
  - `tests/p1_translation_samples/` -> `tests/fixtures/p1_translation_samples/`
  - `tests/.tmp/` -> `tests/tmp/`
- Reorganize docs:
  - `docs/runbook.md` -> `docs/runbooks/backend.md`
  - `docs/planning/` -> `docs/archive/planning/`
- Reorganize deploy env material:
  - `deploy/p0.env.example` -> `deploy/env/p0.env.example`
  - host-specific deployment docs under `deploy/hosts/` if they are not
    current user-facing docs.
- Update `.gitignore`, `.dockerignore`, docs, tests, scripts, and config
  defaults to the new paths.

Validation:

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_llm_client_characterization
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_render_config_characterization
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_golden_sample_manifest
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_p1_translation_sample_manifest
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_backend_logging
```

Additional checks:

```bash
rg "template_configs|template/|prompt/|tests/golden_samples|tests/p1_translation_samples|tests/\\.tmp|\\bdata/" app scripts tests docs README.md deploy docker .env.example
```

Rollback:

- Revert this phase as a unit if resource imports or config defaults break.

Review gate:

- Stop after Phase 1 and confirm the root layout before changing `app/`
  business package boundaries.

## Phase 2: `files` domain sample

Steps:

- Create `app/domains/files/`.
- Move files domain code:
  - `app/core/file_models.py` -> `app/domains/files/models.py`
  - `app/schemas/files.py` -> `app/domains/files/schemas.py`
  - `app/services/files/upload_service.py` -> `app/domains/files/service.py`
  - `app/services/files/retention.py` -> `app/domains/files/retention.py`
  - `app/services/files/pdf_validation.py` -> `app/domains/files/validation.py`
  - `app/api/v1/routers/files.py` -> `app/domains/files/router.py`
- Move the document file repository protocol from central protocols into
  `app/domains/files/repository.py`.
- Update imports in services, routers, tests, and runtime wiring.
- Keep `app/api/v1/router.py` as the route aggregation point and include the
  new domain router.

Validation:

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_artifact_retention
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_database_job_repository
```

Additional checks:

```bash
rg "app\\.core\\.file_models|app\\.schemas\\.files|app\\.services\\.files|app\\.api\\.v1\\.routers\\.files" app tests scripts
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/export_openapi.py
```

Rollback:

- Revert the `files` slice only if imports or OpenAPI contract drift cannot be
  contained locally.

Review gate:

- Stop after Phase 2. Confirm the domain package shape before migrating any
  larger domain.

## Phase 3: Persistence architecture split

Steps:

- Create `app/infrastructure/persistence/{file,sqlite,mysql}/`.
- Split all-purpose adapters by backend and domain/port:
  - jobs
  - job files/artifacts metadata
  - document files
  - document jobs
  - stage messages
  - audit events
  - resource versions
- Move schema bootstrap for sqlite/mysql into backend-specific `schema.py`.
- Update `app/main.py` runtime composition to wire the new adapters.
- Delete or empty old all-purpose repository modules only after `rg` proves
  there are no imports left.

Validation:

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_database_job_repository
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_metadata_shadow_copy
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_artifact_shadow_upload
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_local_file_storage_integrity_check
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_resource_versioning
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend
```

Additional checks:

```bash
rg "FileJobRepository|DatabaseJobRepository|MysqlJobRepository|app\\.repositories" app tests scripts
```

Rollback:

- Roll back backend by backend if a split adapter breaks; do not continue to
  mysql before file/sqlite wiring is stable.

Review gate:

- Stop after Phase 3. This is the highest-risk phase.

## Phase 4: Remaining domain migrations

Recommended order:

1. `audit`
2. `resources`
3. `translation`
4. `document_jobs`
5. `templates`
6. `term_rules`
7. `jobs`

For each domain:

- Move models from `app/core/*_models.py` to the domain.
- Move schemas from `app/schemas/` to the domain.
- Move services from `app/services/<domain>/` to the domain.
- Move router implementation from `app/api/v1/routers/` to the domain.
- Move repository port into the domain.
- Update imports and route aggregation.
- Run the smallest domain-specific tests before moving to the next domain.

Validation examples:

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_document_ir_translation
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_translation_runtime_characterization
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_resource_versioning
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend
```

Rollback:

- Roll back one domain at a time. Do not combine multiple domain migrations in
  one unrecoverable step.

## Phase 5: Cleanup, docs, and spec

Steps:

- Delete obsolete empty packages:
  - `app/schemas/`
  - `app/services/` subpackages that fully moved to domains
  - `app/repositories/` after persistence migration is complete
  - old root resource/entrypoint directories
- Update `.trellis/spec/backend/directory-structure.md`.
- Update `.codestable/architecture/ARCHITECTURE.md` and detailed architecture
  pages to describe the final layout.
- Regenerate `docs/api/openapi.json` if OpenAPI output changed only through
  intentional generation drift.

Validation:

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest discover tests
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/check_release.py
```

Final review:

- Confirm root contains only accepted top-level directories and tool dotfiles.
- Confirm `rg "app\\.schemas|app\\.repositories|app\\.services\\." app tests scripts`
  has no stale imports except intentionally retained transition code.
- Confirm current docs contain new commands and new paths.
