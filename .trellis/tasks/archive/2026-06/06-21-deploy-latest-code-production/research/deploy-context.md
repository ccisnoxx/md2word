# Deploy Context

This task reuses the current hostdzire production release process documented in
`docs/deploy/hostdzire-dmit-md2word.md` and
`docs/deploy/online-first-validation-workflow.md`.

Key constraints:

- GitHub `origin/main` is the deployment source of truth.
- hostdzire is the only host touched for normal code updates.
- `/root/md2word` is a dirty historical worktree and is not the default deploy
  target.
- Each normal release lives in `/root/md2word-releases/<short-sha>`.
- The new release must copy `.env` and `deploy/auth_internal_users.json` from
  the current running release, preserving secrets and operational config.
- The deployment may update only `APP_VERSION` and `DEPLOYMENT_ID` in `.env`.
- Evidence must not include VPS credentials, tokens, passwords, private IPs, or
  raw secret values.
