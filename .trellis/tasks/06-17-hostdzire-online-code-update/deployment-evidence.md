# Hostdzire Online Code Update Evidence

## Deployment

- Target: hostdzire `/root/md2word`.
- Front machine: dmit unchanged.
- Upload method: tar package fallback, with runtime secrets/data excluded.
- Remote backup created: `md2word-pre-deploy-20260617T100328Z.tgz`.
- Backend compose: rebuilt `md2word-p0:latest` and recreated `api` / `worker`.
- Frontend release: `update-20260617T100456Z`.
- Nginx config test: pass; nginx reloaded.

## Validation

- Local `git diff --check`: pass.
- Frontend `npm run build`: pass.
- Hostdzire Compose:
  - `api`: running and healthy.
  - `worker`: running.
  - `mysql`: running and healthy.
  - `redis`: running and healthy.
- Hostdzire local health:
  - `/api/v1/health/live`: status ok.
  - `/api/v1/health/ready`: status ok; `deployment_init_ready=true`; `p0_document_jobs_ready=true`; metadata backend `mysql`; document job worker backend `celery`; no readiness blockers.
  - `/api/v1/health/metrics`: status ok; metadata store `mysql`; artifact storage `local_object`; worker mode `external`.
- Public entry:
  - `https://md2word.962850.xyz/`: returned frontend HTML.
  - `https://md2word.962850.xyz/api/v1/health/live`: status ok.
  - `https://md2word.962850.xyz/api/v1/health/ready`: status ok.
- Release check:
  - `.venv/bin/python scripts/ops/check_release.py --runtime-url https://md2word.962850.xyz`: pass.
  - OpenAPI current, frontend contract check pass, frontend smoke mock pass, targeted unittest pass, runtime readiness pass.

## Notes

- Host system `python3` lacks project dependencies, so release check was executed locally against the public runtime URL.
- Linux tar ignored macOS extended attribute headers during extraction; this did not block deployment.
- Existing deployment metadata still reports `APP_VERSION=2026.06.17-p2` and the prior hostdzire deployment id; `.env` was intentionally not changed.

## 2026-06-18 Update

### Deployment

- Target: hostdzire `/root/md2word`.
- Front machine: dmit unchanged.
- Upload method: tar package fallback; `.git`, `.env`, `deploy/auth_internal_users.json`, runtime data, dependencies, local outputs, test outputs, IDE files, and temporary files excluded.
- Remote backup created: `/root/md2word-backups/md2word-pre-deploy-20260618T030356Z.tgz`.
- Backend compose: rebuilt `md2word-p0:latest` and recreated `api` / `worker`; MySQL and Redis remained running.
- Frontend release: `/var/www/md2word-frontend/releases/update-20260618T030356Z`; `current` symlink updated.
- Nginx config test: pass; nginx reloaded.
- Temporary upload packages and local temporary SSH key were cleaned up after deployment.

### Validation

- Local lightweight checks:
  - `git diff --check`: pass.
  - `.venv/bin/python scripts/ops/export_openapi.py --check --no-diff`: pass after refreshing `docs/api/openapi.json`.
  - `frontend npm run build`: already passed before deployment in this implementation session.
  - Targeted backend unittest for template layout config and renderer style consumption: pass before deployment in this implementation session.
- Hostdzire Compose:
  - `api`: running and healthy.
  - `worker`: running.
  - `mysql`: running and healthy.
  - `redis`: running and healthy.
- Hostdzire local health:
  - `/api/v1/health/live`: status ok.
  - `/api/v1/health/ready`: status ok; `deployment_init_ready=true`; `p0_document_jobs_ready=true`; metadata backend `mysql`; document job worker backend `celery`; no readiness blockers.
  - `/api/v1/health/metrics`: status ok; metadata store `mysql`; artifact storage `local_object`; worker mode `external`.
- Public entry:
  - `https://md2word.962850.xyz/`: returned frontend HTML pointing to the new JS/CSS asset names.
  - `https://md2word.962850.xyz/api/v1/health/live`: status ok.
  - `https://md2word.962850.xyz/api/v1/health/ready`: status ok.
- Release check:
  - `.venv/bin/python scripts/ops/check_release.py --runtime-url https://md2word.962850.xyz`: pass.
  - OpenAPI current, frontend contract check pass, frontend smoke mock pass, targeted unittest pass, runtime readiness pass.
- Online admin template config checks:
  - Unauthenticated `GET /api/v1/templates/default/layout-config`: `403`.
  - Unauthenticated `POST /api/v1/templates/default/layout-config/versions`: `403`.
  - Admin token `GET /api/v1/templates/default/layout-config`: returned `template_id=default`, 18 editable groups, `meta` keys `schema_version` / `template_name` / `output_filename`, and no non-editable fields in `config`.
  - Admin token invalid `POST` containing `schema_version` inside `config`: `400`.
  - Public frontend bundle contains `Word 模板配置中心` and `配置样式`.

### Notes

- Host system `python3` dependency state was not used for release checks; release gate was executed locally against the public runtime URL.
- Linux tar again ignored macOS extended attribute headers during extraction. A separate `COPYFILE_DISABLE=1` frontend dist package was used so the published static release has no `._*` AppleDouble files.
- Existing deployment metadata still reports `APP_VERSION=2026.06.17-p2` and the prior hostdzire deployment id; `.env` was intentionally not changed.
