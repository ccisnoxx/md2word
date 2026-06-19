# Redeploy Hostdzire Project

## Goal

Update the `hostdzire` deployment to the current `origin/main` project code and restart the production Docker Compose stack so the latest md2word API and worker are running.

## Requirements

* Connect to `hostdzire` using the VPS notes supplied by the user.
* Locate the md2word deployment checkout on the remote host.
* Preserve remote secrets, `.env`, persistent Docker volumes, uploaded artifacts, MySQL data, and Redis data.
* Update the deployment checkout to the latest `origin/main`.
* Rebuild and restart the production Docker Compose stack from `docker/prod/docker-compose.yml`.
* Verify the running service with container status and the documented health endpoints.

## Acceptance Criteria

* [x] Remote checkout reports the latest deploy commit from `origin/main`.
* [x] `docker compose --env-file .env -f docker/prod/docker-compose.yml up -d --build` completes on `hostdzire`.
* [x] `docker compose --env-file .env -f docker/prod/docker-compose.yml ps` shows the production services running or healthy.
* [x] `/api/v1/health/live` and `/api/v1/health/ready` respond on the configured local API bind port.

## Definition of Done

* Remote deployment completed or a concrete blocker is reported.
* No local business code changes are made for this task.
* Credentials are not printed in user-facing output.
* Trellis task is archived and journaled after deployment.

## Technical Approach

Use the existing production deployment flow documented in `docs/deploy/p0-docker-deployment.md`: update the remote Git checkout, rebuild the shared `md2word-p0:latest` image, restart the API/worker/MySQL/Redis compose stack, then check health.

Because the existing `/root/md2word` checkout on `hostdzire` had extensive local modifications and untracked files, the deployment used a clean detached worktree at `/root/md2word-releases/bccebdc3` instead of resetting the dirty checkout. The release worktree reuses copied production `.env` and `deploy/auth_internal_users.json`, while Docker volumes remain under the existing `md2word-p0` compose project.

## Out of Scope

* Changing application code or deployment configuration.
* Recreating Docker volumes or deleting persisted data.
* Rotating secrets, changing DNS, or modifying nginx/front-proxy routing.
* Deploying local-only Trellis bookkeeping commits unless explicitly needed.

## Technical Notes

* Local `origin/main` currently contains the incident triage work commit `bccebdc3`.
* Local `main` is ahead of `origin/main` only by Trellis archive/journal bookkeeping commits.
* Production compose file: `docker/prod/docker-compose.yml`.
* Deployment guide: `docs/deploy/p0-docker-deployment.md`.
* Remote `docker compose ps` after deploy: API healthy, MySQL healthy, Redis healthy, worker running.
* Health checks after deploy: `/api/v1/health/live` returned `ok`; `/api/v1/health/ready` returned `ok` with no readiness blockers.
* Runtime OpenAPI includes `document-job-incidents`, confirming the new incident triage API is present in the running image.
* API/worker logs after restart showed only existing Starlette deprecation warnings and normal startup messages.
