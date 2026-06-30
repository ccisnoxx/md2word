# P0 Golden Sample release evidence audit

## Current Status

Status: latest hostdzire release deployed; readiness, Golden Sample preflight, automated 4-sample regression, and admin manual signoff passed.

## Local Evidence Prep

Executed on: 2026-06-29

| Check | Result |
| --- | --- |
| `git status --short --branch` | Working tree contains expected Trellis planning/task files; no business code changes observed. |
| `git diff --check` | Passed. |
| `.venv/bin/python -m unittest tests.test_golden_sample_manifest tests.test_openapi_export.OpenAPIExportTests.test_golden_sample_preflight_release_check_requires_admin_and_p0_runtime` | Passed: 20 tests OK. |
| Golden Sample manifest enabled IDs | `gs-003`, `gs-004`, `gs-006`, `gs-008`. |

## Hostdzire Evidence

Executed on: 2026-06-29

| Evidence | Result |
| --- | --- |
| Local target commit | `20d496ed1df0c1d3eee94c0e6dfac0c0e6653ed3` (`HEAD` / `origin/main` at the time of selection). |
| Current hostdzire release | `/root/md2word-releases/1f072ef`. |
| Current hostdzire release commit | `1f072efd9a7878a024b03035bfa300f289060571`. |
| Release match | Mismatch: current hostdzire release is older than local target commit. |
| Docker Compose baseline | API, worker, MySQL, and Redis containers running; API container healthy. |
| `/api/v1/health/live` | Passed. |
| `/api/v1/health/ready` | Passed with `deployment_init_ready=true`, `p0_document_jobs_ready=true`, `effective_repository_backend=mysql`, `document_jobs_worker_backend=celery`, and no readiness/P0 blockers. |
| `check_release.py --runtime-url --golden-sample-preflight` | Passed on the current hostdzire release. |
| Release check tests | Passed: 170 tests OK. |
| Golden Sample preflight | Passed: 4 manifest samples matched, no missing/orphan PDFs, bearer-token admin auth accepted, runtime readiness OK. |
| Preflight report path | `/root/md2word-releases/1f072ef/tests/tmp/golden_sample_runs/preflight.json`. |

## Latest Release Deployment

Executed on: 2026-06-29

| Evidence | Result |
| --- | --- |
| Deployed release | `/root/md2word-releases/20d496e`. |
| Deployed commit | `20d496ed1df0c1d3eee94c0e6dfac0c0e6653ed3`. |
| Deployment ID | `hostdzire-20260629T070215Z-20d496e`. |
| Docker build/up | Passed; API and worker recreated, MySQL and Redis preserved. |
| Current runtime env after deploy | `/root/md2word-releases/20d496e/.env`. |
| Runtime readiness | Passed after deploy with API healthy. |
| `/api/v1/health/ready` | Passed with `deployment_init_ready=true`, `p0_document_jobs_ready=true`, `effective_repository_backend=mysql`, `document_jobs_worker_backend=celery`, and no readiness/P0 blockers. |
| `check_release.py --runtime-url --golden-sample-preflight` | Passed on deployed release. |
| Release check tests | Passed: 173 tests OK. |
| Golden Sample preflight | Passed: 4 manifest samples matched, no missing/orphan PDFs, bearer-token admin auth accepted, runtime readiness OK. |
| Preflight report path | `/root/md2word-releases/20d496e/tests/tmp/golden_sample_runs/preflight.json`. |

## Golden Sample Regression

Executed on: 2026-06-29

| Evidence | Result |
| --- | --- |
| Release | `/root/md2word-releases/20d496e`. |
| Commit | `20d496ed1df0c1d3eee94c0e6dfac0c0e6653ed3`. |
| Run directory | `/root/md2word-releases/20d496e/tests/tmp/golden_sample_runs/20260629T070506Z`. |
| Report files | `report.json`, `report.md`, and `manual-signoff-template.yaml` exist. |
| DOCX outputs | 4 DOCX files exist. |
| Configured / matched / runnable samples | 4 / 4 / 4. |
| Succeeded / failed | 4 / 0. |
| Pass rate | 100%. |
| Automated chain target | Passed. |
| `p0_release_ready` before signoff | `false`. |
| Blocker before signoff | `admin_manual_word_quality_signoff_required`. |
| DOCX quality flags | `docx_manual_list_markers:10`, `docx_unstyled_heading_candidates:17` on `gs-004`; admin notes are required if signing this sample as pass. |

| Sample | File | Job ID | Result file ID | Status | DOCX openable | Quality flags |
| --- | --- | --- | --- | --- | --- | --- |
| `gs-003` | `OPA228_P1.pdf` | `docjob_9f06bd85fed6` | `file_f4720c056a23` | succeeded | true | none |
| `gs-004` | `OPA228_P2.pdf` | `docjob_c4a4a38fbe23` | `file_123f1132150d` | succeeded | true | `docx_manual_list_markers:10`, `docx_unstyled_heading_candidates:17` |
| `gs-006` | `OPA228_P6.pdf` | `docjob_fdd277dddc0a` | `file_4198179d8d75` | succeeded | true | none |
| `gs-008` | `OPA228_P7.pdf` | `docjob_45cee9763396` | `file_6ae034c1947b` | succeeded | true | none |

## Admin Manual Signoff

Executed on: 2026-06-29

| Evidence | Result |
| --- | --- |
| Signoff file | `/root/md2word-releases/20d496e/tests/tmp/golden_sample_runs/20260629T070506Z/manual-signoff.yaml`. |
| Reviewer role | `admin`. |
| Reviewer | `admin`. |
| Signed at | `2026-06-29T07:16:05Z`. |
| Final signoff | `true`. |
| Passed sample IDs | `gs-003`, `gs-004`, `gs-006`, `gs-008`. |
| Signoff blockers | none. |
| Final `p0_release_ready` | `true`. |
| Final `p0_release_blocker` | none. |

`gs-004` was signed as pass with notes accepting `docx_manual_list_markers:10` and `docx_unstyled_heading_candidates:17` as non-blocking because the generated DOCX opens, remains editable, keeps required content order, has readable TOC/revision-history/list content, and has acceptable header/footer boundaries for P0.

Next evidence needed:

- sync or import this run into Acceptance Center via `06-29-acceptance-center-release-evidence-sync`

## Current Conclusion

`p0_release_ready=true` for hostdzire release `20d496e` and Golden Sample run `20260629T070506Z`. The remaining handoff is Acceptance Center evidence sync.
