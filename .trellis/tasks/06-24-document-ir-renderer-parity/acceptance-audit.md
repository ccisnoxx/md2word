# DocumentIR renderer parity acceptance audit

## Conclusion

2026-06-24 local conclusion: the phase-3 implementation is ready for
hostdzire P0 Golden Sample validation. The formal chain under
`document_jobs -> DocumentIR -> app/services/renderer/*` is covered by targeted
tests, and the local release check passes.

This audit does not claim `p0_release_ready=true`. Full Golden Sample
conversion, standard-render screenshots, and admin sign-off require the
hostdzire API/Worker/MySQL/Redis/Celery/MinerU environment.

## Completion Evidence

- Shared pure rules live under `app/conversion/docx_rules/` and are consumed by
  both local runtime and formal renderer paths.
- `DocumentJobExecutionService` passes `DocumentIRRenderOptions` into
  `DocumentIRWordRenderer`, including subscript config path and document
  language.
- `MinerUToDocumentIRService` preserves nested v2 pages, rich content fields,
  captions, footnotes, image paths, table continuations, wide-table hints, and
  page orientation facts in DocumentIR.
- `DocumentIRWordRenderer` covers heading/list/TOC/formula/subscript,
  caption/footnote, editable table, long/wide table, landscape, and two-column
  layout behavior through direct renderer tests.
- document_jobs regression tests prove generated Word metadata and OOXML
  semantics through `/api/v1/document-jobs` style worker execution, not only a
  direct renderer call.
- The P0 Golden Sample acceptance entrypoint remains
  `scripts/ops/run_golden_sample_regression.py` against the formal API path.

## Local Verification

| Command | Result |
|---|---|
| `.venv/bin/python -m unittest tests.test_document_ir_mineru_converter_layout` | 4 tests OK |
| `.venv/bin/python -m unittest tests.test_document_ir_word_renderer_layout` | 25 tests OK |
| `.venv/bin/python -m unittest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_worker_saves_mineru_raw_ir_and_image_assets tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_worker_generated_word_keeps_renderer_ooxml_semantics tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_worker_passes_subscript_config_to_document_ir_renderer` | 3 tests OK |
| `.venv/bin/python -m unittest tests.test_golden_sample_manifest tests.test_openapi_export.OpenAPIExportTests.test_golden_sample_preflight_release_check_requires_admin_and_p0_runtime` | 20 tests OK |
| `git diff --check` | OK |
| `.venv/bin/python scripts/ops/check_release.py` | `Release check report ok: True`; targeted unittest suite 168 tests OK |

Warnings observed: existing FastAPI/Starlette deprecation warnings only.

## External Pending Gate

Run on hostdzire after deploying the target commit:

```bash
GOLDEN_SAMPLE_USERNAME=admin \
GOLDEN_SAMPLE_PASSWORD='<admin-password>' \
.venv/bin/python scripts/ops/check_release.py \
  --runtime-url "http://127.0.0.1:${MD2WORD_API_BIND_PORT:-18000}" \
  --golden-sample-preflight \
  --golden-sample-preflight-output tests/tmp/golden_sample_runs/preflight.json

GOLDEN_SAMPLE_USERNAME=admin \
GOLDEN_SAMPLE_PASSWORD='<admin-password>' \
.venv/bin/python scripts/ops/run_golden_sample_regression.py
```

The release gate is complete only after admin applies `manual-signoff.yaml` to
the same run directory and the generated report shows `p0_release_ready=true`.
