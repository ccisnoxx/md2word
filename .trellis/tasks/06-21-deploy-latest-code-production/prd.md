# Deploy Latest Code To Production

## Goal

Deploy the latest local `main` state to the hostdzire production deployment and
verify that the public md2word service is running the intended commit.

## What I Already Know

- User asked to update online code and redeploy.
- Current local branch is `main` and was clean before task creation.
- Standard production path is documented in
  `docs/deploy/hostdzire-dmit-md2word.md` and
  `docs/deploy/online-first-validation-workflow.md`.
- Normal code updates only touch `hostdzire`; `dmit`, DNS, nginx stream,
  WireGuard, certificates, and secrets are out of scope unless verification
  proves they are broken.
- Production releases use `/root/md2word-releases/<short-sha>` on hostdzire,
  cloning from `git@github.com:ccisnoxx/md2word.git`.
- The previous release evidence shows the current runtime was deployed from
  `/root/md2word-releases/fecd3337`.

## Assumptions

- GitHub `origin/main` is the source of truth for production release code.
- Existing hostdzire `.env`, internal user JSON, MySQL, Redis, Docker volumes,
  nginx, and certificates should be preserved.
- This deployment updates runtime code only; it does not intentionally rotate
  secrets, change routing, or run full Golden Sample conversion unless runtime
  validation indicates that is necessary.

## Requirements

- Confirm local `main` is clean except for this Trellis task record.
- Confirm the target commit and push it to `origin/main`.
- Confirm `origin/main` points at the target commit before touching hostdzire.
- On hostdzire, create or reuse `/root/md2word-releases/<short-sha>` for the
  target commit.
- Copy `.env` and `deploy/auth_internal_users.json` from the currently running
  release.
- Update non-sensitive deployment tracking fields:
  - `APP_VERSION=<short-sha>`
  - `DEPLOYMENT_ID=hostdzire-<utc-run-id>-<short-sha>`
- Rebuild and restart the production Docker Compose stack.
- Verify Docker Compose services, loopback health, public health, and release
  gate.
- Do not write VPS credentials, tokens, passwords, private IPs, or secret env
  values into tracked files or chat output.

## Acceptance Criteria

- [x] `origin/main` contains the intended target commit.
- [x] hostdzire release directory for the target commit exists and checks out
      the intended commit.
- [x] Production compose services are running after rebuild/restart.
- [x] hostdzire loopback `/api/v1/health/live` and `/api/v1/health/ready` pass.
- [x] Public `https://md2word.962850.xyz/api/v1/health/live` and `/ready` pass.
- [x] Release gate runner passes against the running runtime.
- [x] Deployment evidence is recorded without secrets.

## Definition Of Done

- Deployment completed or a concrete blocker is reported.
- Worktree is clean aside from deployment task/evidence bookkeeping.
- Task can be archived after evidence is recorded.

## Out Of Scope

- Changing app code.
- Rotating secrets or changing `.env` values other than non-sensitive release
  tracking fields.
- Changing `dmit`, DNS, certificates, WireGuard, or nginx routing.
- Deleting historical release directories.
- Full Golden Sample conversion regression unless runtime validation indicates
  it is needed.

## Technical Notes

- Deployment guide: `docs/deploy/hostdzire-dmit-md2word.md`
- Docker deployment guide: `docs/deploy/p0-docker-deployment.md`
- Validation workflow: `docs/deploy/online-first-validation-workflow.md`
- Previous evidence: `.trellis/tasks/archive/2026-06/06-21-deploy-latest-md2word-to-hostdzire/deployment-evidence.md`
