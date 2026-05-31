---
doc_type: acceptance
task: 05-31-phase-9-final-regression-parent-closure
status: completed
parent: 05-31-project-directory-restructure
completed_at: 2026-05-31
---

# Phase 9 acceptance

## Summary

Phase 9 completed the remaining ownership cleanup after Phase 1-8. `app/core/`
now contains only infrastructure primitives, and the remaining central API v1
schema module has been split into route-specific auth/health schema companion
modules.

External HTTP contracts and model fields were preserved; OpenAPI release
validation reported no snapshot change.

## Changes

- Moved auth user context records from `app/core/auth_models.py` to
  `app/services/auth/models.py`.
- Moved Document IR records from `app/core/document_ir_models.py` to
  `app/services/document_ir/models.py`.
- Moved renderer template config records from
  `app/core/template_config_models.py` to
  `app/services/renderer/template_config.py`.
- Replaced central `app/api/v1/schemas.py` with
  `app/api/v1/routers/auth_schemas.py` and
  `app/api/v1/routers/health_schemas.py`.
- Updated imports, direct tests, Trellis backend spec, CodeStable architecture,
  and API docs/manifest.
- Updated parent task notes and Phase 9 Trellis artifacts.

## Validation

Command:

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend tests.test_document_ir_translation
```

Result: passed. Ran 95 tests.

Command:

```bash
rg -n "app\\.core\\.(auth_models|document_ir_models|template_config_models)|app\\.api\\.v1\\.schemas|app/api/v1/schemas\\.py" app tests scripts docs .trellis/spec/backend .codestable/architecture -S
```

Result: passed. No matches.

Command:

```bash
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/check_release.py
```

Result: passed. `ok: True`; OpenAPI snapshot current; `changed: False`; 58
paths and 87 schemas; targeted release unittest ran 28 tests.

Command:

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest discover tests
```

Result: passed. Ran 256 tests.

## Residual Risk

- The repository still has the broad uncommitted Phase 1-8 restructure diff.
  Phase 9 worked with that state and did not normalize unrelated prior-phase
  edits.
- Historical archived planning docs were not separately scanned; current code,
  tests, scripts, docs, backend spec, and CodeStable architecture were scanned.
