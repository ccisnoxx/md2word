---
doc_type: acceptance
task: 05-31-phase-6-final-integration-acceptance
status: completed
parent: 05-31-project-directory-restructure
completed_at: 2026-05-31
---

# Phase 6 acceptance

## Summary

Phase 6 performed the final integration acceptance pass for the project
directory restructure. No runtime code changes were required. The only fixes
were current Trellis backend spec references that still described pre-restructure
paths or modules.

## Changes

- Updated `.trellis/spec/backend/database-guidelines.md` from `data/` and old
  core job modules to `var/`, `app/domains/jobs/*`, and
  `app/infrastructure/persistence/*`.
- Updated `.trellis/spec/backend/quality-guidelines.md` to refer to owning
  domain/API schema modules instead of the removed central schema package.
- Updated `.trellis/spec/backend/error-handling.md` examples to the migrated
  jobs domain modules.
- Updated `.trellis/spec/backend/logging-guidelines.md` to point the business
  logger example at `app/domains/jobs/stage.py`.

## Audit Results

Command:

```bash
rg -n "app\\.schemas|app\\.repositories|app\\.services\\.(jobs|templates|term_rules|translation|translation_profiles|resource_versions|document_jobs|audit)|app\\.core\\.(job_models|job_paths|resource_models|audit_models|translation_models|template_models|rule_models|document_job_models|file_models)" app tests scripts
```

Result: no matches.

Command:

```bash
rg -n -P "(?<!resources/)template_configs/|(?<!resources/)template/|(?<!resources/)prompt/|tests/golden_samples|tests/p1_translation_samples|tests/\\.tmp|\\bdata/" app tests scripts docs README.md deploy docker .env.example .trellis/spec/backend .codestable/architecture
```

Result: one accepted match for the current `resources/template_configs/`
directory entry in `.trellis/spec/backend/directory-structure.md`; no stale old
root path guidance remained.

Command:

```bash
rg -n "app/schemas|app/repositories|app/services/(jobs|templates|term_rules|translation|translation_profiles|resource_versions|document_jobs|audit)|app/core/(job_models|job_paths|resource_models|audit_models|translation_models|template_models|rule_models|document_job_models|file_models)" .trellis/spec/backend .codestable/architecture docs/dev docs/deploy docs/runbooks docs/api docs/testing
```

Result: remaining matches are accepted negative/current-history references that
state central `app/schemas` and `app/repositories` are removed and must not be
recreated.

## Validation

Command:

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend
```

Result: passed, 93 tests.

Command:

```bash
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/check_release.py
```

Result: passed. OpenAPI snapshot is current, with 58 paths and 87 schemas; the
targeted release unittest group passed 28 tests.

## Residual Risk

Phase 6 did not rerun full `unittest discover`; release validation and the
FastAPI backend suite passed, and Phases 1-5 already performed broader
validation. Historical archived planning docs may still contain old paths by
design.
