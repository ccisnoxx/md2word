# P2 acceptance audit

## Scope

P2 covers internal single-tenant operationalization for hostdzire: deployment traceability, online evidence gate, admin status visibility, docs/runbook updates, and P0/P1 closeout notes. It does not change the P0 Word quality line or the P1 translation QA workflow.

## Local implementation evidence

Completed locally:

- Added non-sensitive deployment metadata to `Settings`, `/api/v1/health/ready`, and `/api/v1/health/metrics`.
- Surfaced deployment version/id/environment/start time on the System Status page.
- Added `scripts/ops/run_p2_online_gate.py` to aggregate live/ready/metrics/ops-alerts, `check_release.py`, P0 preflight, P1 preflight, and optional public dmit health checks into `tests/tmp/p2_online_runs/<run_id>/`.
- Updated `.env.example`, README, health API docs, backend runbook, online-first workflow, and stale P0 Golden Sample report status.
- Updated `.trellis/spec/backend/quality-guidelines.md` with the executable P2 online health and release gate contract.
- Created this Trellis task, PRD, research note, and curated implementation/check context.

## Local verification

All checks below are no-service checks. They did not start local frontend/backend, local Docker, MySQL, Redis/Celery, worker, Playwright, or the full conversion chain.

| Check | Result | Notes |
|---|---:|---|
| `PYTHONPYCACHEPREFIX=/private/tmp/md2word-pyc .venv/bin/python -m py_compile app/core/config.py app/api/v1/routers/health_schemas.py app/services/health_service.py scripts/ops/run_p2_online_gate.py` | pass | Uses project `.venv` Python 3.11. |
| `PYTHONPYCACHEPREFIX=/private/tmp/md2word-pyc .venv/bin/python -m unittest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_health_ready_reports_runtime_dependencies tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_health_metrics_reports_runtime_counters tests.test_openapi_export.OpenAPIExportTests.test_p2_online_gate_collects_runtime_evidence` | pass | Covers health deployment metadata and P2 gate report assembly. |
| `npm run --prefix frontend test:unit -- --run` | pass | 6 files, 17 tests. |
| `npx vue-tsc --noEmit` from `frontend/` | pass | Validates new frontend health deployment types. |
| `PYTHONPYCACHEPREFIX=/private/tmp/md2word-pyc .venv/bin/python scripts/ops/export_openapi.py --check --no-diff` | pass | OpenAPI snapshot current after deployment schema update. |
| `PYTHONPYCACHEPREFIX=/private/tmp/md2word-pyc .venv/bin/python -m unittest tests.test_openapi_export` | pass | 6 tests, including runtime readiness and P2 gate. |
| `PYTHONPYCACHEPREFIX=/private/tmp/md2word-pyc .venv/bin/python scripts/ops/check_release.py` | pass | OpenAPI, frontend contract, smoke mock contract, 31 targets / 139 tests. |
| `git diff --check` | pass | No whitespace errors. |

## Hostdzire deployment evidence

Completed on hostdzire on 2026-06-17 UTC:

- Created a pre-P2 backup at `/root/md2word-backups/md2word-pre-p2-20260617T080539Z.tgz`.
- `rsync` was unavailable on hostdzire, so the upload used a tar package with the same production excludes for `.git`, `.env`, internal user file, runtime data, local virtualenvs, frontend test output, and temporary artifacts.
- Set non-sensitive deployment traceability fields in hostdzire `.env`: `APP_VERSION=2026.06.17-p2` and a P2 `DEPLOYMENT_ID`.
- Rebuilt and restarted `docker/prod/docker-compose.yml`; `api`, `worker`, `mysql`, and `redis` were all up, with `api` and `mysql` healthy.
- Built the frontend locally, uploaded `frontend/dist`, published it to `/var/www/md2word-frontend/releases/p2-20260617T080923Z`, and updated `/var/www/md2word-frontend/current`.
- Fixed the frontend release directory ownership and mode after the tar extraction preserved local `501:staff` and `700`, which initially caused public `/` to return `403`.

## Hostdzire runtime evidence

Direct backend checks after deploy:

- `/api/v1/health/live`: `ok`
- `/api/v1/health/ready`: `status=ok`, `deployment_init_ready=true`, `p0_document_jobs_ready=true`, `effective_repository_backend=mysql`, `document_jobs_worker_backend=celery`, `translation_available=true`, `readiness_blockers=[]`, `readiness_warnings=[]`
- `/api/v1/health/metrics`: collected MySQL/local object/external worker metrics; `document_jobs_failed=1` was already present as a non-critical operational warning.

Public entry checks after frontend permission fix:

- `https://md2word.962850.xyz/`: HTTP 200, returns the Vue app HTML.
- `https://md2word.962850.xyz/assets/index-MkqzFyyT.js`: HTTP 200.
- `https://md2word.962850.xyz/api/v1/health/live`: `ok`.
- `https://md2word.962850.xyz/api/v1/health/ready`: `status=ok`, deployment metadata present, MySQL + Celery baseline active.

P2 gate evidence:

- Run id: `20260617T081408Z`
- Local artifact copy: `artifacts/hostdzire-p2-online-gate-20260617T081408Z/report.md` and `report.json`
- `p2_online_gate_ready=true`
- blockers: `none`
- warnings: `document_jobs_failed_present`
- checks passed: `live`, `ready`, `metrics`, `ops_alerts`, `public`, `release_check`, `p0_preflight`, `p1_preflight`
- Note: the remote P2 gate used `--no-release-check-unittests` because the full local `check_release.py` had already passed; the remote gate still ran runtime release checks plus P0/P1 preflights against hostdzire.

## Current remaining risks

- `document_jobs_failed_present` remains a watch-level operational warning; it did not block readiness or the P2 online gate, but should be reviewed during routine task governance.
- `environment` still reports `dev`; the effective public deployment guard is `public_deployment_mode=single_tenant_public` and the required MySQL/Celery gates pass. Decide separately whether to rename the environment label for hostdzire.
- P1 formal beta signoff still requires three real samples and admin review; P2 treats this as a separate admin validation gate, not a P2 implementation blocker.
- The worktree contains many pre-existing P0/P1 dirty files. P2 touched files should be reviewed separately before committing.
