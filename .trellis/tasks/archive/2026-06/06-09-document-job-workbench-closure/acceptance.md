# Document Job Workbench Closure - Acceptance

## Decision

Accepted for this child task.

The implementation closes the planned document-job workbench scope: server-owned action availability, unarchive, clone/rerun as a new job, global breadcrumb navigation, list/detail workbench controls, docs/OpenAPI refresh, and focused tests.

This acceptance does not approve or exercise a real PDF-MinerU parse, translation provider call, or Word generation main workflow.

## Inputs Reviewed

- `.trellis/tasks/06-09-document-job-workbench-closure/prd.md`
- `.trellis/tasks/06-09-document-job-workbench-closure/design.md`
- `.trellis/tasks/06-09-document-job-workbench-closure/implement.md`
- Parent roadmap docs under `.trellis/tasks/06-09-md2word-product-maturity-roadmap/`
- Current backend, frontend, test, and API-doc changes in the document-job workbench surface.

## Scope Accepted

- `DocumentJobResponse` now includes computed `available_actions` with stable action keys and `enabled` / `disabled_reason`.
- New additive API actions exist for `POST /api/v1/document-jobs/{job_id}/unarchive` and `POST /api/v1/document-jobs/{job_id}/clone`.
- Clone/rerun creates a new job, preserves the source job, tracks `source_job_id`, and remains separate from retry.
- Archive remains non-destructive; unarchive restores default-list visibility.
- `/jobs` adds date range filtering, quick filters, batch cancel, row clone/unarchive actions, and action gating from `available_actions`.
- `/jobs/:jobId` uses detail tabs, event filters, expanded `JobActions`, and a separate `重新发起为新任务` dialog.
- Global breadcrumb covers task, QA, configuration, term proposal, and system-status routes touched by this work.
- API docs and OpenAPI were refreshed.

## Acceptance Matrix

| Criterion | Status | Evidence |
| --- | --- | --- |
| Operator can search/filter by status, QA status, time range, open detail, download, and inspect failures from `/jobs`. | PASS | Frontend build passed; online `/jobs` smoke verified list, filters, date-range DOM, row actions, and visible job data. |
| Admin can use server-allowed batch retry/cancel/archive and see disabled reasons when disallowed. | PASS | Batch cancel UI added beside existing retry/archive; table selection and buttons read `available_actions`; backend response test covers disabled reasons. Online smoke did not submit mutating batch actions. |
| Single job detail supports cancel, retry, archive, unarchive, and clone/rerun from `available_actions`. | PASS | `JobActions` renders all actions; online detail smoke verified action visibility; unarchive/clone backend behavior covered by focused tests. |
| Retry and clone/rerun stay separate in UI, API, and data records. | PASS | Separate `/retry` and `/clone` endpoints; separate retry and clone dialogs; clone test verifies source retry count/source job unchanged. |
| Clone creates a new job and preserves traceability. | PASS | Focused backend clone test verifies new job id, `source_job_id`, source file reuse, and source job immutability. |
| Archived task can be restored through unarchive. | PASS | Focused backend unarchive test verifies archive fields are cleared, default list visibility is restored, and event/audit evidence is written. |
| Global breadcrumb covers job list/detail/QA and configuration children. | PASS | New layout breadcrumb component; online smoke verified jobs and job detail breadcrumb; build covers route references. |
| No real delete, task-file delete, batch upload, or standalone preset page. | PASS | Diff review found no delete UI/API addition for this task, no batch upload UI, and no standalone preset page. |
| Design and implement docs exist before implementation acceptance. | PASS | `design.md` and `implement.md` exist and were reviewed before this acceptance. |

## Verification Run

- PASS: focused backend tests:

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_response_includes_server_action_availability tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_unarchive_restores_default_list_and_writes_audit tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_clone_creates_new_job_without_mutating_source tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_clone_rejects_expired_source_and_reports_disabled_reason tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_clone_explicit_resource_selection_requires_admin
```

- PASS: frontend build:

```bash
cd frontend && npm run build
```

- PASS: OpenAPI export:

```bash
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/export_openapi.py
```

- PASS: release check:

```bash
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/check_release.py
```

- PASS: whitespace check:

```bash
git diff --check
```

Observed non-blocking warnings:

- Vite/Rollup emitted existing third-party pure-annotation warnings.
- Vite emitted the existing chunk-size warning.

## Online Deployment Smoke

The current code was deployed to the online project host for smoke testing.

- Production source and frontend were backed up before update.
- Deployment backup timestamp: `20260609T213730Z`.
- API health after deployment: healthy.
- Public frontend route `/jobs` returned HTTP 200 and served the newly built asset bundle.
- Read-only API smoke against `GET /api/v1/document-jobs?page=1&page_size=3&include_archived=true` verified jobs include `source_job_id` and `available_actions` keys: `download`, `retry`, `cancel`, `archive`, `unarchive`, `clone`.
- Browser smoke used short-lived admin auth and task `docjob_d86b732f2103`.
- Browser checks passed:
  - `/jobs` list loads without redirecting to login.
  - Breadcrumb, task list, date-range control, batch cancel, clone, and unarchive controls render.
  - `/jobs/docjob_d86b732f2103` detail loads with breadcrumb, tabs, and all job actions.
  - Clone dialog opens as `重新发起为新任务` and was closed without submitting.
  - Mobile detail view loads and renders breadcrumb/action/tab text.
- Smoke screenshots:
  - `/private/tmp/md2word-jobs-list-smoke.png`
  - `/private/tmp/md2word-job-detail-smoke.png`
  - `/private/tmp/md2word-job-detail-mobile-smoke.png`

Online smoke intentionally did not submit clone, retry, cancel, archive, unarchive, upload, download, or batch action POSTs.

## Safety Statement

This acceptance did not run PDF-MinerU parsing, MinerU recovery query/download, translation provider calls, Word generation, batch upload, real task deletion, task-scoped file deletion, or cleanup/delete workflows.

Online verification was limited to deployment health, read-only API checks, and UI navigation/dialog rendering. The clone dialog was opened but not submitted.

Secrets and VPS credential values are not recorded in this acceptance.

## Residual Risks

- Clone reuses source file metadata; if retention has removed physical object content while metadata remains valid, later execution can still fail through the normal job execution path.
- Action availability can become stale between render and click; endpoint validation remains authoritative.
- Online mutation paths for clone/unarchive/batch actions were not submitted by design. Their behavior is accepted from focused backend tests and local build/type validation.
- The remote deployment is a direct source copy rather than a git checkout; rollback should use the recorded deployment backup timestamp.
