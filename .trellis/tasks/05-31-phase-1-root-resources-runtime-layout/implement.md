---
doc_type: implement-plan
task: 05-31-phase-1-root-resources-runtime-layout
status: approved
parent: 05-31-project-directory-restructure
---

# Phase 1 implementation plan

## Rules

- Do not start until this child task is reviewed and explicitly approved for
  implementation.
- Do not add compatibility shims for old root paths.
- Do not delete local runtime data under `data/`; leave it alone unless the user
  explicitly asks to remove it.
- Keep each move mechanical and update imports/references immediately after the
  move.
- Use `/Users/sc/miniconda3/envs/md2word/bin/python` for Python verification.

## Step 0: Baseline

Commands:

```bash
git status --short
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_llm_client_characterization
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_render_config_characterization
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_golden_sample_manifest
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_p1_translation_sample_manifest
```

If baseline tests fail because of unrelated dirty worktree state, record the
failure and continue only with narrower import/path checks approved by the user.

## Step 1: Move local runners

Actions:

- Create `scripts/dev/`.
- Move:
  - `run_api.py` -> `scripts/dev/run_api.py`
  - `run_worker.py` -> `scripts/dev/run_stage_worker.py`
  - `run_document_worker.py` -> `scripts/dev/run_document_worker.py`
- Ensure each runner still injects `.python_packages` using repository root,
  not `scripts/dev/`.
- Update docs and examples that call the old root scripts.

Checks:

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m py_compile scripts/dev/run_api.py scripts/dev/run_stage_worker.py scripts/dev/run_document_worker.py
rg "run_api\\.py|run_worker\\.py|run_document_worker\\.py" README.md docs deploy docker scripts tests app
```

## Step 2: Move conversion runtime config

Actions:

- Move `config.py` -> `app/conversion/runtime_config.py`.
- Update import sites in conversion runtime and tests.
- Keep the file header accurate after the move.
- Confirm `ROOT_DIR` resolves to repository root.

Checks:

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_llm_client_characterization
rg "from config import|import config\\b|APP_CONFIG|ROOT_DIR" app tests scripts
```

## Step 3: Move versioned resources

Actions:

- Create `resources/` subdirectories.
- Move templates, template config, term-rule assets, translation terms, and
  prompts to their target locations.
- Update `app/core/config.py`, `app/conversion/runtime_helpers.py`,
  `app/conversion/runtime/llm_client.py`, tests, manifests, scripts, and docs.

Checks:

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_render_config_characterization
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_llm_client_characterization
rg "template_configs|template/|prompt/" app tests scripts README.md docs deploy docker .env.example
```

## Step 4: Change runtime root to var

Actions:

- Update `Settings.data_dir` default to `var`.
- Update default runtime paths from `data/...` to `var/...` where they are
  literal defaults or examples.
- Update `.gitignore` and `.dockerignore`.
- Do not move or delete existing local `data/`.

Checks:

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_backend_logging
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_local_file_storage_integrity_check
rg "\\bdata/" app tests scripts README.md docs deploy docker .env.example
```

## Step 5: Move test fixtures

Actions:

- Move `tests/golden_samples/` -> `tests/fixtures/golden_samples/`.
- Move `tests/p1_translation_samples/` -> `tests/fixtures/p1_translation_samples/`.
- Move `tests/.tmp/` -> `tests/tmp/`.
- Update manifests, tests, regression script defaults, and docs.

Checks:

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_golden_sample_manifest
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_p1_translation_sample_manifest
rg "tests/golden_samples|tests/p1_translation_samples|tests/\\.tmp" app tests scripts README.md docs .codestable .trellis
```

## Step 6: Reorganize docs and deploy files

Actions:

- Move `docs/runbook.md` -> `docs/runbooks/backend.md`.
- Move `docs/planning/` -> `docs/archive/planning/`.
- Move `deploy/p0.env.example` -> `deploy/env/p0.env.example`.
- Move provider/host-specific deploy notes under `deploy/hosts/` if they are
  host instructions rather than general docs.
- Update current docs, README, and deploy references.

Checks:

```bash
rg "docs/runbook\\.md|docs/planning|deploy/p0\\.env\\.example" README.md docs deploy docker scripts tests app .trellis .codestable
```

## Step 7: Final targeted verification

Commands:

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_llm_client_characterization
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_render_config_characterization
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_golden_sample_manifest
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_p1_translation_sample_manifest
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_backend_logging
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_local_file_storage_integrity_check
```

Final stale-reference audit:

```bash
rg "run_api\\.py|run_worker\\.py|run_document_worker\\.py|template_configs|template/|prompt/|tests/golden_samples|tests/p1_translation_samples|tests/\\.tmp|docs/runbook\\.md|docs/planning|deploy/p0\\.env\\.example|\\bdata/" app tests scripts README.md docs deploy docker .env.example
```

Expected final state:

- Stale references in active code/current docs are gone.
- Any remaining old path references are only inside historical archive files or
  explicit planning notes.
- No product behavior changes were introduced.
