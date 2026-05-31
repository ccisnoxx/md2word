---
doc_type: implement-plan
task: 05-31-phase-6-final-integration-acceptance
status: approved
parent: 05-31-project-directory-restructure
---

# Phase 6 implementation plan

## Step 0: Recheck task and tree state

Commands:

```bash
git status --short
python3 .trellis/scripts/task.py current --source
```

Expected:

- Existing dirty worktree reflects Phases 1-5.
- Phase 6 is the active or current planning task after creation.

## Step 1: Audit removed imports and old paths

Commands:

```bash
rg "app\\.schemas|app\\.repositories|app\\.services\\.(jobs|templates|term_rules|translation|translation_profiles|resource_versions|document_jobs|audit)|app\\.core\\.(job_models|job_paths|resource_models|audit_models|translation_models|template_models|rule_models|document_job_models|file_models)" app tests scripts
rg "template_configs|template/|prompt/|tests/golden_samples|tests/p1_translation_samples|tests/\\.tmp|\\bdata/" app tests scripts docs README.md deploy docker .env.example .trellis/spec/backend .codestable/architecture
```

Expected:

- No active code imports removed packages.
- Current docs/specs do not describe old locations as current. Historical
  archive hits are reviewed but do not need edits.

## Step 2: Fix stale current documentation/spec references

Actions:

- Update backend spec files beyond `directory-structure.md` if they still name
  old `data/`, `app/repositories`, `app/schemas`, or old domain service paths.
- Update current architecture/docs files if the audit finds stale path guidance.
- Do not edit archived planning docs solely to rewrite history.

Checks:

```bash
rg "app/schemas|app/repositories|template_configs|template/|prompt/|\\bdata/" .trellis/spec/backend .codestable/architecture docs/dev docs/deploy docs/runbooks docs/api docs/testing
```

## Step 3: Run final validation

Commands:

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/check_release.py
```

If the release check fails because OpenAPI needs regeneration from an already
implemented intentional restructure, run:

```bash
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/export_openapi.py
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/check_release.py
```

## Step 4: Record acceptance

Actions:

- Add `acceptance.md` with the audit commands, test commands, results, and any
  residual risks.
- Update this task's PRD checkboxes after evidence is collected.
