# Deployment Evidence

## Summary

- Date: 2026-06-21
- Target commit: `cdc49e2a3d12afc0489c20e7b310b3a3e03c6381`
- Target version: `cdc49e2`
- Deployment id: `hostdzire-20260621T074328Z-cdc49e2`
- Release directory: `/root/md2word-releases/cdc49e2`
- Compose project: `md2word-p0`
- Scope: code-only production redeploy; existing `.env`, internal user JSON,
  MySQL, Redis, Docker volumes, nginx, certificates, and routing preserved.

No VPS credentials, tokens, passwords, private IPs, or secret env values are
recorded in this evidence.

## Local Preflight

- Confirmed local target commit on `main`: `cdc49e2a3d12afc0489c20e7b310b3a3e03c6381`.
- Ran `.venv/bin/python scripts/ops/check_release.py` before deployment.
- Result: `ok: True`.
- Checks passed:
  - OpenAPI snapshot current.
  - Frontend API contracts match core OpenAPI fields.
  - Frontend smoke mock covers core contract scenarios.
  - Targeted unittests passed: 146 tests.
- Observed warnings were existing Starlette deprecation warnings.

## GitHub Sync

- Pushed `main` to `origin/main`.
- Confirmed remote branch with `git ls-remote origin refs/heads/main`.
- Remote result:
  `cdc49e2a3d12afc0489c20e7b310b3a3e03c6381 refs/heads/main`.
- Local tracking ref was refreshed with `git fetch origin main` after the push.

## Remote Deployment

- Created or reused `/root/md2word-releases/cdc49e2`.
- Checked out detached target commit
  `cdc49e2a3d12afc0489c20e7b310b3a3e03c6381`.
- Copied `.env` and `deploy/auth_internal_users.json` from the running release.
- Updated only non-sensitive release tracking fields:
  - `APP_VERSION=cdc49e2`
  - `DEPLOYMENT_ID=hostdzire-20260621T074328Z-cdc49e2`
- Ran Docker Compose build and `up -d` with
  `docker/prod/docker-compose.yml`.

## Runtime Verification

Final Compose state:

- `api`: running, healthy, image `md2word-p0:latest`, release working directory
  `/root/md2word-releases/cdc49e2/docker/prod`.
- `worker`: running, image `md2word-p0:latest`, release working directory
  `/root/md2word-releases/cdc49e2/docker/prod`.
- `mysql`: running, healthy.
- `redis`: running, healthy.

Loopback health:

- `/api/v1/health/live`: `status=ok`, `app_name=md2word_file`.
- `/api/v1/health/ready`:
  - `status=ok`
  - `version=cdc49e2`
  - `deployment_id_present=true`
  - `deployment_init_ready=true`
  - `effective_repository_backend=mysql`
  - `document_jobs_worker_backend=celery`
  - `p0_document_jobs_ready=true`
  - `readiness_blockers=[]`
  - `p0_document_jobs_blockers=[]`

Public health:

- `https://md2word.962850.xyz/api/v1/health/live`:
  `status=ok`, `app_name=md2word_file`.
- `https://md2word.962850.xyz/api/v1/health/ready`:
  - `status=ok`
  - `version=cdc49e2`
  - `deployment_id_present=true`
  - `deployment_init_ready=true`
  - `effective_repository_backend=mysql`
  - `document_jobs_worker_backend=celery`
  - `p0_document_jobs_ready=true`
  - `readiness_blockers=[]`
  - `p0_document_jobs_blockers=[]`

Log check:

- Checked the last 300 lines for `api` and `worker`.
- No `ERROR`, `CRITICAL`, `Traceback`, `Unhandled`, `Exception`, `panic`, or
  `fatal` signals were found.

## Release Gate

Ran the release gate from the production image against the running API:

```bash
python scripts/ops/check_release.py \
  --runtime-url http://md2word-p0-api-1:8000
```

Result: `ok: True`.

Checks passed:

- OpenAPI snapshot current.
- Frontend API contracts match core OpenAPI fields.
- Frontend smoke mock covers core contract scenarios.
- Targeted unittests passed: 146 tests.
- Runtime readiness passed with MySQL + Celery P0 baseline:
  - `deployment_init_ready=true`
  - `p0_document_jobs_ready=true`
  - `effective_repository_backend=mysql`
  - `document_jobs_worker_backend=celery`
  - `readiness_blockers=[]`
  - `p0_document_jobs_blockers=[]`

Observed warnings were existing Starlette deprecation warnings.

## Notes

- The first remote readiness helper used `python`, which is not installed on
  the host; it was rerun with `python3`.
- Public readiness dependency checks are exposed as flat fields under
  `dependency_checks`; evidence above records the corrected extraction.
- Full Golden Sample conversion was not run because this was a code-only
  redeploy and the release gate plus runtime readiness passed.
- No `dmit`, DNS, nginx stream, WireGuard, certificate, secret, or routing
  changes were made.
