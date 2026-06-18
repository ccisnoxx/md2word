# P1 Translation QA Governance Beta Acceptance Audit

## Stage 1 - Local Implementation Slice

Status: completed locally and verified on hostdzire smoke path.

Completed changes:

- Added admin-only `debug_full_text` enforcement for `en2zh_pdf_to_word` create/clone paths.
- Extended translation QA evidence with debug archive expiry, expired state, full-text marker, and `debug_full_text_enabled`.
- Updated QA frontend types and QA detail display so reviewers can distinguish debug archive off/missing/expired/active.
- Added admin upload UI control for P1 full-text debug archive, default off and only submitted for translation mode.
- Added P1-only online regression script: `scripts/ops/run_p1_translation_regression.py`.
- Updated README, API docs, fixture docs, online-first validation workflow, OpenAPI snapshot, smoke mock, and release checks.
- Fixed health readiness semantics so `translation_available=true` now requires `TRANSLATION_PROVIDER_BACKEND=openai_compatible`, OpenAI-compatible client configuration, and the translation prompt.
- Added `translation_provider_backend` and `translation_debug_archive_enabled` to health evidence, and made P1 preflight block when provider/debug archive prerequisites are missing.
- Hardened the P1 regression script against transient read-only polling/download `ConnectionError`/timeout/stream errors observed during long provider calls.

Validation run locally:

- `UV_CACHE_DIR=/private/tmp/uv-cache uv pip install -r requirements.txt`
- `UV_CACHE_DIR=/private/tmp/uv-cache uv run python scripts/ops/export_openapi.py`
- `UV_CACHE_DIR=/private/tmp/uv-cache uv run python -m py_compile scripts/ops/run_p1_translation_regression.py app/domains/document_jobs/service.py app/domains/document_jobs/schemas.py`
- `UV_CACHE_DIR=/private/tmp/uv-cache uv run python -m unittest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_en2zh_worker_translates_ir_and_saves_ai_audit_artifacts tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_en2zh_debug_full_text_is_admin_only tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_translation_qa_reads_existing_artifacts_and_updates_review_state tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_clone_rejects_operator_inheriting_debug_full_text tests.test_p1_translation_sample_manifest`
- `cd frontend && npx vue-tsc --noEmit`
- `cd frontend && npm run test:unit`
- `UV_CACHE_DIR=/private/tmp/uv-cache uv run python scripts/ops/check_release.py`
- `git diff --check`

Observed result:

- OpenAPI export passed and updated `docs/api/openapi.json`.
- Targeted P1 backend tests passed.
- Frontend type check passed.
- Frontend unit tests passed: 6 files / 17 tests.
- Release check passed: OpenAPI, frontend contract, frontend smoke mock contract, and 31 targeted unittest entries.
- `git diff --check` passed.

## Stage 2 - Hostdzire Validation

Status: smoke passed; formal beta intentionally blocked on admin-managed sample/signoff inputs.

Online deployment and checks:

- Uploaded the P1 file slice to `/root/md2word` on hostdzire after backing up the remote tree to `/root/md2word-p1-backup-20260617T064405Z.tgz`.
- Rebuilt/restarted Docker Compose API and worker containers.
- Set hostdzire P1 runtime prerequisites:
  - `TRANSLATION_DEBUG_ARCHIVE_ENABLED=true`
  - `TRANSLATION_PROVIDER_BACKEND=openai_compatible`
- `/api/v1/health/ready` passed with:
  - `effective_repository_backend=mysql`
  - `document_jobs_worker_backend=celery`
  - `p0_document_jobs_ready=true`
  - `translation_provider_backend=openai_compatible`
  - `translation_debug_archive_enabled=true`
  - `translation_available=true`
  - `readiness_blockers=[]`
- Remote release gate passed:
  - `docker run --rm --user 0 --network host -v /root/md2word:/workspace -w /workspace md2word-p0:latest python scripts/ops/check_release.py --runtime-url http://127.0.0.1:18000`
  - Result: `ok=True`, OpenAPI current, frontend contract/mock checks passed, 139 tests passed, runtime readiness passed with MySQL + Celery P0 baseline.

P1 online regression evidence:

- Smoke preflight passed:
  - `tests/tmp/p1_translation_runs/preflight.json`
  - manifest available samples `1`, required samples `1`
  - auth role `admin`
  - runtime MySQL + Celery + provider + debug archive + en2zh all available
- Smoke regression passed:
  - run dir: `/workspace/tests/tmp/p1_translation_runs/20260617T070930Z`
  - sample: `p1-en-001`
  - job: `docjob_e2601cb0d1ed`
  - result file: `file_c409b5d4f745`
  - `succeeded=1`, `failed=0`, `automated_chain_met_target=true`
  - `docx_openable=true`
  - `qa_available=true`
  - `ai_call_count=1`
  - `term_trace_count=3`
  - `term_hit_rate=1.0`
  - matched terms: `input offset voltage`, `slew rate`
  - `debug_full_text_enabled=true`
  - `debug_archive_file_count=1`
  - `debug_archive_contains_full_text=true`
  - `debug_archive_expired=false`
  - `source_comparison_available=true`
  - DOCX SHA256: `sha256:50fd80618fec69374529f350c23298e3b0a24f6957fe78065c7cdaef3f2b0831`
- Formal preflight intentionally failed with only the expected blocker:
  - `P1_TRANSLATION_FORMAL=1 ... run_p1_translation_regression.py --preflight`
  - blocker: `p1_available_sample_count_below_required`
  - available samples `1`, required samples `3`
  - auth/runtime checks passed.

Required next steps for formal P1 beta:

1. Admin provides enough real technical datasheet PDFs and marks at least 3 manifest samples as `source_status=available`.
2. Run P1 formal regression with `P1_TRANSLATION_FORMAL=1`.
3. Admin reviewer checks generated DOCX/QA/debug evidence and applies manual translation quality signoff.
4. Re-run formal regression with signoff so `p1_beta_ready=true`.

Remaining risks:

- Formal P1 beta cannot be signed off until real datasheet samples are added and admin manual translation quality signoff is applied; current manifest has one synthetic smoke sample.
- hostdzire runtime prerequisites are now enabled and checked by preflight, but provider latency is real; the smoke sample took about 142 seconds end-to-end.
- `debug_full_text=true` requires `TRANSLATION_DEBUG_ARCHIVE_ENABLED=true` online and should remain limited to admin-reviewed P1 samples.
- The current local worktree contains unrelated dirty files from P0; upload/commit must separate P1 changes from existing work.
