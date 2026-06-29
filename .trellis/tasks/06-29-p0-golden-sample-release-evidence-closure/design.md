# P0 Golden Sample release evidence closure design

## Purpose

Close the current P0 PDF-to-Word release evidence loop by running the existing Golden Sample validation process on hostdzire or an equivalent staging environment, preserving the generated evidence, and recording whether the current release is actually ready.

This is an evidence and operations task. It does not introduce new product behavior, API contracts, schema changes, sample scope, or renderer logic.

## Boundaries

- In scope:
  - Run local static/unit checks that do not require real services.
  - Deploy or identify the target release on hostdzire/staging.
  - Run runtime readiness and Golden Sample preflight.
  - Run the existing 4-sample Golden Sample regression.
  - Coordinate admin manual DOCX review and apply machine-readable signoff.
  - Update task-local evidence notes and the Golden Sample status report with the current conclusion.
  - Hand off report fields needed by the Acceptance Center sync task.
- Out of scope:
  - Adding or changing Golden Sample PDFs.
  - Expanding P0 beyond technical datasheets/electronic documents.
  - Fixing conversion defects found during the run.
  - Importing evidence into Acceptance Center directly.
  - Storing secrets, signed URLs, generated DOCX, rendered screenshots, or private host details in git.

## Existing Contracts

### Sample Contract

`tests/fixtures/golden_samples/manifest.yaml` is the source of truth for the P0 canonical suite. The enabled samples are:

- `gs-003` / `OPA228_P1.pdf`
- `gs-004` / `OPA228_P2.pdf`
- `gs-006` / `OPA228_P6.pdf`
- `gs-008` / `OPA228_P7.pdf`

The target success rate is `1.0`. Missing samples are blockers.

### Preflight Contract

The release preflight uses either:

```bash
.venv/bin/python scripts/ops/check_release.py \
  --runtime-url "http://127.0.0.1:${MD2WORD_API_BIND_PORT:-18000}" \
  --golden-sample-preflight \
  --golden-sample-preflight-output tests/tmp/golden_sample_runs/preflight.json
```

or the equivalent direct regression preflight:

```bash
.venv/bin/python scripts/ops/run_golden_sample_regression.py \
  --preflight \
  --preflight-output tests/tmp/golden_sample_runs/preflight.json
```

Preflight must verify sample availability, admin auth, `/health/ready`, MySQL metadata, Celery worker mode, and `p0_document_jobs_ready=true`.

### Regression Contract

The regression command is:

```bash
GOLDEN_SAMPLE_USERNAME=admin \
GOLDEN_SAMPLE_PASSWORD='<admin-password>' \
.venv/bin/python scripts/ops/run_golden_sample_regression.py
```

It writes a unique `tests/tmp/golden_sample_runs/<run_id>/` directory containing:

- `report.json`
- `report.md`
- `manual-signoff-template.yaml`
- downloaded successful DOCX files
- machine-readable DOCX quality evidence in the report

The run is not release-ready until manual signoff is valid.

### Manual Signoff Contract

Admin copies `manual-signoff-template.yaml` to `manual-signoff.yaml`, fills reviewer fields, sets `final_signoff: true`, and sets each sample `verdict` to `pass` only after opening the generated DOCX and reviewing quality.

The signoff is applied to the same run directory:

```bash
.venv/bin/python scripts/ops/run_golden_sample_regression.py \
  --apply-manual-signoff tests/tmp/golden_sample_runs/<run_id>
```

`p0_release_ready=true` requires:

- automated chain target met
- 4/4 samples succeeded
- 4/4 DOCX openable
- valid admin signoff
- all quality flags either absent or explicitly accepted in admin notes

## Data Flow

1. Select target commit/release and deploy or identify it on hostdzire.
2. Confirm runtime readiness through `/health/ready` and `check_release.py --runtime-url`.
3. Run Golden Sample preflight; stop if blockers exist.
4. Run the 4-sample regression against the live API.
5. Preserve the run directory and report outputs.
6. Admin opens the generated DOCX files and optional standard-render screenshots/PDFs.
7. Admin fills and applies `manual-signoff.yaml`.
8. The updated `report.json` / `report.md` becomes the current P0 evidence.
9. Task-local evidence notes summarize run id, release id, sample results, signoff, blockers, and Acceptance Center handoff fields.
10. `docs/testing/pdf-to-word-golden-sample-acceptance-report.md` is updated with the current conclusion.

## Operational Safeguards

- Do not run real Golden Sample conversion locally; local checks are limited to static/unit/script contract checks.
- Do not continue past preflight failure.
- Do not overwrite a failed run directory; reruns must create a new timestamped run.
- Do not edit `report.json` manually to force success.
- Do not commit `tests/tmp/golden_sample_runs/`, generated DOCX, rendered PNG/PDF evidence, secrets, signed URLs, or private host details.
- Use placeholders such as `<hostdzire-ssh>` and `<admin-password>` in task notes and docs.

## Failure Handling

- Runtime/preflight blocker: record blocker names and stop before submitting conversion jobs.
- Sample job failure: preserve the run directory, record job id/failure stage/error code, and stop release-ready claims.
- DOCX quality flag: require admin notes if signed as pass; otherwise keep `p0_release_ready=false`.
- Missing admin signoff: leave the run blocked with `admin_manual_word_quality_signoff_required`.
- Conversion defect requiring code changes: open or move to a separate implementation task; do not fix inside this evidence task without approval.

## Handoff To Acceptance Center Sync

This task should produce enough information for `06-29-acceptance-center-release-evidence-sync` to register or import the current P0 evidence:

- title/source for P0 Golden Sample canonical suite
- report path or URL
- run id
- status: passed, failed, or unknown
- summary
- blockers and warnings
- reviewer and review timestamp

The actual Acceptance Center import/sync remains outside this task.
