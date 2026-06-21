# Deploy latest md2word to hostdzire

## Goal

Deploy the latest `main` branch state to the hostdzire production machine and
persist the repeatable rollout procedure in repository documentation.

## What I Already Know

- Local `main` is ahead of `origin/main` by one commit, so hostdzire cannot pull
  the latest code from GitHub until the local commit is pushed.
- Existing deploy docs define hostdzire as the deployment machine at
  `/root/md2word`; dmit is only the public forwarding machine for normal code
  updates.
- Production uses Docker Compose with
  `/root/md2word/docker/prod/docker-compose.yml` and `/root/md2word/.env`.
- The public entry is `https://md2word.962850.xyz`.
- Private VPS login information is stored outside the repository and must not be
  copied into tracked files, task notes, or user-facing replies.

## Assumptions

- The GitHub repository `git@github.com:ccisnoxx/md2word.git` is the deployment
  source of truth for this release.
- hostdzire either already has `/root/md2word` cloned, or can clone the
  repository via GitHub SSH.
- Existing `.env`, internal users JSON, MySQL, Redis, nginx, and certificate
  configuration on hostdzire should be preserved.

## Requirements

- Push the local latest commit to GitHub before asking hostdzire to pull.
- Confirm whether hostdzire already has the repository deployed.
- Update or clone `/root/md2word` on hostdzire from GitHub.
- Rebuild and restart the Docker Compose stack on hostdzire.
- Validate local backend health from hostdzire and public health through dmit.
- Document the successful fast rollout flow for future releases.

## Acceptance Criteria

- [x] `origin/main` contains the latest local release commit.
- [x] hostdzire `/root/md2word-releases/fecd3337` is at the intended Git commit.
- [x] Docker Compose services are up after rebuild/restart.
- [x] `live` and `ready` health checks pass from hostdzire loopback.
- [x] Public `https://md2word.962850.xyz/api/v1/health/live` responds.
- [x] Release/deploy docs contain a quick future rollout procedure that avoids
      secrets and references the private VPS file only by path.

## Out of Scope

- Changing dmit routing, WireGuard, DNS, nginx certificates, or hostdzire `.env`
  unless deployment verification proves they are broken.
- Running full Golden Sample or translation regression unless readiness fails or
  the deployment changes runtime conversion behavior.
- Adding or modifying application features.

## Technical Notes

- Existing docs inspected:
  - `docs/deploy/hostdzire-dmit-md2word.md`
  - `docs/deploy/online-first-validation-workflow.md`
  - `docs/deploy/p0-docker-deployment.md`
- Relevant quality constraint: do not log or document secrets, tokens, passwords,
  raw private host details, or resolved sensitive values.
