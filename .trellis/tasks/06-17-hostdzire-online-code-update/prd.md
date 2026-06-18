# Update hostdzire online code

## Goal

Update the already-deployed md2word instance on hostdzire with the current local repository code, while preserving hostdzire runtime secrets, data, uploads, MySQL/Redis state, and the dmit front-machine routing.

## What I Already Know

- `/Users/sc/work_file/bak_file/VPS.txt` contains private connection information for two VPS machines.
- dmit is only the public front machine. Ordinary code updates must not modify dmit.
- hostdzire is the deployment machine, with the project deployed at `/root/md2word`.
- The established deployment path is documented in `docs/deploy/online-first-validation-workflow.md` and `docs/deploy/hostdzire-dmit-md2word.md`.
- Deployment runs through Docker Compose at `docker/prod/docker-compose.yml`.
- Existing runtime secrets and account files live on hostdzire and must not be overwritten.

## Requirements

- Read private VPS information only locally; do not print or persist credentials, IPs, passwords, or tokens in task artifacts or chat.
- Sync current local code to `hostdzire:/root/md2word`.
- Exclude `.git`, `.env`, `deploy/auth_internal_users.json`, runtime data, node modules, local virtualenvs, local output, temporary files, and IDE files from upload.
- Do not use `--delete` unless explicitly requested.
- Do not modify dmit unless health checks prove the front proxy is broken.
- Rebuild/restart the hostdzire production Compose stack after sync.
- Check hostdzire local API health and public dmit entry health after deployment.
- Record only non-sensitive command outcomes in final response.

## Acceptance Criteria

- [ ] hostdzire receives the current code changes without overwriting secrets or runtime data.
- [ ] Docker Compose rebuild/restart succeeds on hostdzire.
- [ ] `docker compose ps` shows API/worker/MySQL/Redis running, with no obvious fresh fatal errors.
- [ ] hostdzire local `/api/v1/health/live` and `/api/v1/health/ready` respond successfully.
- [ ] public `https://md2word.962850.xyz/api/v1/health/live` and `/ready` respond successfully.
- [ ] Any remaining blocker or warning is reported clearly.

## Out of Scope

- Editing application code as part of this deployment task.
- Changing dmit nginx/WireGuard routing.
- Rotating secrets, changing `.env`, or editing internal accounts.
- Running full Golden Sample or P1 regression unless needed after health checks.
- Committing or pushing code.

## Technical Notes

- Deployment guide: `docs/deploy/online-first-validation-workflow.md`.
- Host topology guide: `docs/deploy/hostdzire-dmit-md2word.md`.
- Production compose: `docker/prod/docker-compose.yml`.
- Docker notes: `docker/README.md`.
