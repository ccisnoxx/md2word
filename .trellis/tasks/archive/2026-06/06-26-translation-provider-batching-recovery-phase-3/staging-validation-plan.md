# Staging Validation Plan

## Scope

Use hostdzire or an equivalent staging deployment to validate Phase 1/2 provider batch recovery on the original 32-page failure sample or a private equivalent long PDF.

Local development should not start API, worker, MySQL, Redis/Celery, MinerU, browser smoke, or real translation provider calls for this evidence.

## Inputs

Required private inputs, kept outside git:

- long PDF sample, preferably the original 32-page failure sample;
- private P1 manifest pointing to that sample;
- admin or operator credentials / bearer token for the target runtime;
- deployed commit / `APP_VERSION` / `DEPLOYMENT_ID`.

The private manifest should follow the existing P1 format and can be passed through `P1_TRANSLATION_MANIFEST`. Example shape:

```yaml
schema_version: 1
sample_root: /secure/path/to/private/pdfs
default_mode: en2zh_pdf_to_word
default_document_language: en
default_term_version_id: en2zh@v1
term_file: resources/term_rules/translation_terms.csv
target_sample_count: 1
required_checks:
  - provider_batch_diagnostics
  - term_hit_rate
  - structure_invariant
  - editable_word
samples:
  - id: private-long-en-001
    filename: original-32-page-failure.pdf
    title: Private long PDF regression
    source_status: available
    tags: [en, long_pdf, provider_batch_recovery]
    expected_terms: []
    acceptance_focus:
      - Provider batch diagnostics are recorded in report.json and report.md.
      - Long PDF does not run as one oversized provider request.
      - Current leaf batches succeed before job success.
```

Do not commit the private manifest if it contains customer-identifying filenames or paths.

## Command

Run on hostdzire or staging after deploying the target commit:

```bash
P1_TRANSLATION_BASE_URL="http://127.0.0.1:${MD2WORD_API_BIND_PORT:-18000}" \
P1_TRANSLATION_USERNAME=admin \
P1_TRANSLATION_PASSWORD='<admin-password>' \
P1_TRANSLATION_MANIFEST=/secure/path/to/private-long-pdf-manifest.yaml \
P1_TRANSLATION_FORMAL=0 \
P1_TRANSLATION_DEBUG_FULL_TEXT=0 \
P1_TRANSLATION_JOB_TIMEOUT_SECONDS=7200 \
.venv/bin/python scripts/ops/run_p1_translation_regression.py
```

Use `P1_TRANSLATION_BEARER_TOKEN` instead of password if the operator already has a token.

## Evidence To Record

From the generated run directory:

- `report.json`
- `report.md`
- job id
- deployment `APP_VERSION` / `DEPLOYMENT_ID`
- sample id and page count
- job terminal status and elapsed seconds
- `summary.translation_batch_diagnostics`
- per-sample `translation_batch_summary`
- per-batch sanitized rows: status, page range, item/char count, attempt, finish_reason, retryable/truncation flags, provider_call_budget, error summary, AI call log count

Allowed report evidence includes file IDs and counts. Do not copy PDF contents, prompt, provider response, source text, translated text, debug archive content, signed URLs, object storage locations, passwords, or bearer tokens.

## Pass / Warning / Blocker

Pass:

- job status is `succeeded`;
- `translation_batch_diagnostics.available=1`;
- total batch count is greater than zero;
- current leaf batches are all `succeeded`;
- generated DOCX is openable;
- report contains no diagnostics blockers.

Warning:

- long PDF succeeds but `translation_batch_truncation_not_observed` appears. This means bounded batching worked, but the live provider did not reproduce truncation during this run. Keep existing automated split tests as complementary evidence.

Blocker:

- job status is `failed` / `canceled`;
- `translation_batch_diagnostics_unavailable`;
- `translation_batch_diagnostics_empty` for a translation job;
- any current leaf batch is `failed`;
- every current leaf batch is `succeeded` but the job does not advance to rendering/result output.

## Follow-Up

If a blocker appears, collect only sanitized evidence:

- `job_id`
- `generation`
- affected `batch_id`
- page range
- attempt count
- `finish_reason`
- `error_code` / shortened `error_message`
- AI call log file id count
- recent job events and trace id

Then use the runbook provider batch diagnostics section to decide whether to run task-level retry or escalate finalizer/provider investigation.
