# P0 Word Delivery Quality Beta Acceptance Audit

Last updated: 2026-06-17

## Scope

This audit tracks the current evidence against `prd.md`. It does not redefine the P0 goal: release readiness still requires the 4-sample Golden Sample suite to pass in a real API/MySQL/Celery environment and receive admin manual sign-off.

## Current Status

| Area | Status | Evidence |
|---|---|---|
| Product scope | Verified locally | README, P0 guide, backend runbook, Golden Sample fixtures, and PRD all state technical datasheet / electronics scope and explicitly exclude generic PDF quality. |
| Canonical sample set | Verified locally | `preflight-current.json` manifest check passes with `OPA228_P1.pdf`, `OPA228_P2.pdf`, `OPA228_P6.pdf`, and `OPA228_P7.pdf`; no missing or orphan PDF. |
| Release automation | Verified locally | `scripts/ops/check_release.py` passed with OpenAPI, frontend contracts, smoke mock, and 26 targeted unittest targets / 133 executed tests. |
| Renderer quality mechanics | Verified by targeted tests | `tests.test_text_render_characterization`, `tests.test_document_ir_word_renderer_layout`, `tests.test_page_layout_characterization`, `tests.test_render_table_from_html_characterization`, and `tests.test_golden_sample_manifest` passed together with 93 tests. |
| DOCX quality evidence | Verified by targeted tests | Golden Sample report tests and Document Jobs backend tests verify DOCX quality evidence, flags, editable-content detection, image-only suspicion, headings, numbering, TOC leaders, table semantics, landscape sections, and LaTeX residue detection. |
| Admin-only task delete | Verified by targeted tests | `test_document_job_delete_requires_admin_preview_and_removes_owned_files` verifies operator direct delete denial and admin preview/confirmation/audit behavior. |
| Frontend delete visibility and quality display | Verified by targeted tests/build | `npm run test:unit -- src/utils/format.test.ts src/utils/displayText.test.ts` passed with 6 tests; `npm run build` passed with only known Vite/Rollup warnings. |
| Production baseline gate | Verified by targeted tests | Health/config tests verify production blocks non-MySQL metadata and eager worker, and allows complete MySQL + Celery readiness. |
| Online-first validation workflow | Documented | `docs/deploy/online-first-validation-workflow.md` defines local edit -> upload to hostdzire -> Docker restart -> runtime gate -> Golden Sample -> admin sign-off. |
| Local full-stack / frontend smoke | Skipped by decision | The current machine is not a valid full-stack validation environment because local frontend/backend startup and MySQL/Redis/Celery services are unavailable. Do not treat local smoke, frontend Playwright smoke, or live service tests as required local evidence for this task. |
| Runtime readiness on this machine | Not ready | `preflight-current.json` shows `golden_sample_api_unreachable` because `http://127.0.0.1:8000` is not running. |
| Golden Sample auth on this machine | Not ready | `preflight-current.json` shows `golden_sample_auth_missing`; no admin password or bearer token is configured. |
| Real Golden Sample conversion after this change set | Not verified | Requires running API + MySQL + Celery + MinerU + admin credentials. |
| Admin manual Word quality sign-off | Not verified | Requires admin reviewer to inspect the 4 generated DOCX files and apply `manual-signoff.yaml`. |

## PRD Acceptance Matrix

| PRD acceptance item | Current result | Required final evidence |
|---|---|---|
| `gs-003`, `gs-004`, `gs-006`, `gs-008` complete through `direct_pdf_to_word` | Blocked by local environment | `scripts/ops/check_release.py --runtime-url <api> --golden-sample-preflight` passes, then `scripts/ops/run_golden_sample_regression.py` reports all 4 `succeeded`. |
| All 4 generated DOCX files are openable | Blocked by local environment | Golden Sample `report.json` / `report.md` show 4/4 `docx_openable=true`. |
| All 4 generated DOCX files are editable, not full-page screenshots | Blocked by local environment | Golden Sample report shows editable-content evidence for all 4 and `image_only_suspected_samples=0`, or admin notes a non-blocking exception. |
| Admin reviewer records passing manual quality verdict for all 4 samples | Blocked by admin sign-off | `manual-signoff.yaml` has `reviewer_role=admin`, `final_signoff=true`, and 4 `verdict: pass`; `p0_release_ready=true` after `--apply-manual-signoff`. |
| 2026-06-03 quality gaps are resolved or admin-accepted as non-blocking | Partially verified by unit/integration tests, not by real samples | Golden Sample DOCX quality flags are empty or every passed flagged sample has admin notes explaining the release decision. |
| Final DOCX is close to source layout while following Word standards | Partially verified by renderer tests, not by real samples | Admin manual quality pass for all 4 samples, using Word-standard structure as the higher priority when visual fidelity conflicts with maintainability. |
| Operator cannot see/execute task delete | Verified locally | Frontend action visibility follows `available_actions`; backend returns `403 role_forbidden` for operator direct delete. |
| Admin guarded task delete works | Verified locally | Backend targeted test covers preview, reason, confirmation phrase, preview hash, result, physical-safe cleanup, metadata, events, and audit. |
| Job detail exposes useful quality/diagnostic information | Verified locally | Backend stores `generated_word.metadata.docx_quality` / `quality_flags`; frontend format tests cover labels and flagged review state. |
| MySQL + Celery + single-worker deployment path documented | Verified locally | README, backend runbook, deploy guide, health docs, and P0 integration guide describe MySQL + Celery baseline and single-worker scope. |
| `/health/ready` reports no blocker and `p0_document_jobs_ready=true` before release | Not verified on this machine | Runtime release check passes against the target environment with MySQL metadata and Celery worker. |
| Docs describe 4-sample canonical P0 gate | Verified locally | Active README/runbooks/testing docs and Golden Sample fixtures are aligned to 4 OPA228 samples, not 10-20 samples. |
| New integration docs do not direct users to legacy `/api/v1/jobs` | Verified locally | Active runbooks mark `/api/v1/jobs` as legacy and direct new integration to Files + Document Jobs. |

## Final Release Commands

Run these on hostdzire after uploading the current local change set and restarting Docker Compose:

```bash
GOLDEN_SAMPLE_USERNAME=admin \
GOLDEN_SAMPLE_PASSWORD='<admin-password>' \
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/check_release.py \
  --runtime-url http://127.0.0.1:${MD2WORD_API_BIND_PORT:-18000} \
  --golden-sample-preflight \
  --golden-sample-preflight-output tests/tmp/golden_sample_runs/preflight.json
```

Then run the real canonical suite:

```bash
GOLDEN_SAMPLE_USERNAME=admin \
GOLDEN_SAMPLE_PASSWORD='<admin-password>' \
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/run_golden_sample_regression.py
```

After admin review, apply sign-off on the same run directory:

```bash
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/run_golden_sample_regression.py \
  --apply-manual-signoff tests/tmp/golden_sample_runs/<run_id>
```

The P0 release can be marked ready only when `report.json` / `report.md` show `p0_release_ready=true`.

## Local Validation Boundary

Do not continue trying to validate this task by starting local frontend/backend services or connecting to local MySQL/Redis/Celery. The local machine is only used for code-level checks, static contract checks, targeted unit/integration tests that do not require real services, and manifest/preflight evidence that can run without a live API.

The remaining evidence must be collected on hostdzire where API, MySQL, Redis/Celery, MinerU, and admin credentials are available. Follow `docs/deploy/online-first-validation-workflow.md`; do not use the local machine as the service validation target.

## Known Remaining Blockers

- `golden_sample_auth_missing`: no admin Golden Sample password or bearer token is configured in the current local shell.
- `golden_sample_api_unreachable`: no local API is listening at `http://127.0.0.1:8000`.
- Local MySQL/Redis/Celery services are unavailable and should not be used as the validation target.
- Real sample quality and admin final sign-off remain unproven until the current local change set is uploaded to hostdzire and the commands above pass there.
