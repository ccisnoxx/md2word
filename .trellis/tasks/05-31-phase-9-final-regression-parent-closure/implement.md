---
doc_type: implement-plan
task: 05-31-phase-9-final-regression-parent-closure
status: approved
parent: 05-31-project-directory-restructure
---

# Phase 9 implementation plan

## Step 0: Confirm task and worktree state

Commands:

```bash
git status --short
python3 .trellis/scripts/task.py current --source
python3 .trellis/scripts/task.py list
```

Expected:

- Existing dirty worktree reflects completed prior phases.
- Phase 9 is current and in progress before implementation continues.

## Step 1: Move remaining non-infrastructure models out of core

Actions:

- Move auth records to `app/services/auth/models.py`.
- Move Document IR records to `app/services/document_ir/models.py`.
- Move renderer template config records to
  `app/services/renderer/template_config.py`.
- Update all imports and direct tests.

## Step 2: Remove the central API v1 schema file

Actions:

- Create route-specific `app/api/v1/routers/auth_schemas.py`.
- Create route-specific `app/api/v1/routers/health_schemas.py`.
- Delete `app/api/v1/schemas.py`.
- Update auth/health routers, health service, tests, docs, and specs.

## Step 3: Validate

Commands:

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend tests.test_document_ir_translation
rg -n "app\\.core\\.(auth_models|document_ir_models|template_config_models)|app\\.api\\.v1\\.schemas" app tests scripts docs .trellis/spec/backend .codestable/architecture
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/check_release.py
```

Expected:

- Targeted tests pass.
- Stale-import scan returns no active-code or current-doc references.
- Release validation passes, or any exact blocker is recorded.

## Step 4: Record closure

Actions:

- Add `acceptance.md` with validation commands, results, changes, and residual
  risks.
- Update Phase 9 PRD acceptance checkboxes.
- Add a parent PRD note that Phase 9 completed core narrowing and central
  schema elimination.
- Mark Phase 9 `task.json` completed locally to match the prior child task
  style, without archiving or committing.
