# Deployment Evidence

## Release

- GitHub `origin/main`: `fecd3337d0346008e162917271513a24a2a09ce9`
- hostdzire release directory: `/root/md2word-releases/fecd3337`
- Previous running release: `/root/md2word-releases/f967f21`
- Compose project: `md2word-p0`
- Runtime publish port: `127.0.0.1:18000`

## Actions

- Pushed local `main` to GitHub and confirmed `origin/main` points at the target commit.
- Created a fresh hostdzire release directory by cloning `git@github.com:ccisnoxx/md2word.git`.
- Checked out the target commit in detached HEAD state.
- Copied `.env` and `deploy/auth_internal_users.json` from the previous running release.
- Updated non-sensitive release tracking fields:
  - `APP_VERSION=fecd3337`
  - `DEPLOYMENT_ID=hostdzire-20260621T035122Z-fecd3337`
- Built `md2word-p0:latest`.
- Recreated API and Worker containers; MySQL and Redis stayed running and healthy.

## Verification

- `docker compose ps` showed:
  - `md2word-p0-api-1`: running, healthy, `127.0.0.1:18000->8000`
  - `md2word-p0-worker-1`: running
  - `md2word-p0-mysql-1`: running, healthy
  - `md2word-p0-redis-1`: running, healthy
- hostdzire loopback `GET /api/v1/health/live`: `{"status":"ok","app_name":"md2word_file"}`
- hostdzire loopback `GET /api/v1/health/ready`:
  - `deployment.version=fecd3337`
  - `deployment_init_ready=true`
  - `p0_document_jobs_ready=true`
  - `effective_repository_backend=mysql`
  - `document_jobs_worker_backend=celery`
  - `readiness_blockers=[]`
  - `p0_document_jobs_blockers=[]`
- Public `GET https://md2word.962850.xyz/api/v1/health/live`: `ok`
- Public `GET https://md2word.962850.xyz/api/v1/health/ready`: `version=fecd3337`, blockers empty.
- Release gate runner:
  - Command shape: production image + mounted release directory + empty `.env` overlay.
  - Result: `Release check report ok: True`
  - OpenAPI snapshot current.
  - Frontend API contracts match OpenAPI.
  - Frontend smoke mock covers core contract scenarios.
  - Targeted unittest passed: 145 tests.
  - Runtime readiness passed with MySQL + Celery P0 baseline.

## Notes

- `/root/md2word` exists but is a dirty historical worktree and was not reset or overwritten.
- Full Golden Sample regression was not run in this deployment because the release did not change the conversion quality path; runtime readiness and release gate passed.
- No VPS credentials, API tokens, internal passwords, or private key material were written into tracked files.
