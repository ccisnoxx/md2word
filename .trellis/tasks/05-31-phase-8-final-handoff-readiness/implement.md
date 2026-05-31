---
doc_type: implement-plan
task: 05-31-phase-8-final-handoff-readiness
status: approved
parent: 05-31-project-directory-restructure
---

# Phase 8 implementation plan

## Step 0: Confirm task and tree state

Commands:

```bash
git status --short
python3 .trellis/scripts/task.py current --source
python3 .trellis/scripts/task.py list
```

Expected:

- Existing dirty worktree reflects completed prior phases.
- Phase 8 is linked under the parent task and becomes started after planning.

## Step 1: Audit stale path and package references

Commands:

```bash
rg -n -P "(?<!resources/)template_configs/|(?<!resources/)template/|(?<!resources/)prompt/|tests/golden_samples|tests/p1_translation_samples|tests/\\.tmp|\\bdata/" app tests scripts docs README.md deploy docker .env.example .trellis/spec/backend .codestable/architecture
rg -n "app\\.schemas|app\\.repositories|app\\.services\\.(jobs|templates|term_rules|translation|translation_profiles|resource_versions|document_jobs|audit)|app\\.core\\.(job_models|job_paths|resource_models|audit_models|translation_models|template_models|rule_models|document_job_models|file_models)" app tests scripts docs .trellis/spec/backend .codestable/architecture
```

Expected:

- No current stale references remain, except accepted negative or historical
  references that explicitly describe removed old paths/packages.
- Any real drift is patched in the smallest owning file.

## Step 2: Validate release readiness

Command:

```bash
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/check_release.py
```

Expected:

- Release validation passes.
- If it fails, record the exact command and blocker in `acceptance.md`.

## Step 3: Record handoff

Actions:

- Add `acceptance.md` with audit commands, validation results, and residual
  risks.
- Update Phase 8 PRD acceptance checkboxes.
- Add a parent PRD note that Phase 8 completed the final handoff-readiness
  audit.
- Mark Phase 8 `task.json` completed locally to match the prior child task
  style, without archiving or committing.
