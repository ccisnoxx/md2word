# md2word Product Maturity Roadmap Closeout

## Result

Accepted as the current internal-portal product baseline.

The original roadmap is no longer an open implementation backlog. Its first three product maturity child tasks have been implemented and archived:

- `document-job-workbench-closure`
- `translation-qa-review-loop`
- `config-governance-ux-consolidation`

This closeout adds the final internal-portal packaging layer:

- Frontend branding no longer presents the workbench with early-stage labels.
- The file retention admin page is reorganized into `文件库`, `容量与策略`, and `清理执行` tabs.
- Dangerous file cleanup controls are kept in the explicit cleanup execution view.
- Maintainer-facing internal portal runbook exists at `docs/runbooks/internal-portal.md`.

## Current Product Shape

md2word is now a company-internal document conversion and governance portal:

- `operator` users work from tasks, translation QA, and terminology suggestions.
- `admin` users additionally manage configuration, audit logs, system status, operations, and file cleanup.
- Authentication remains internal account JSON/PBKDF2/JWT.
- The first production-oriented deployment profile remains single-tenant internal use with MySQL metadata, local object artifacts, Celery worker, admin-gated ops, and explicit audit trails.

## Deferred Scope

The following are explicitly out of the first formal internal portal baseline:

- Company SSO.
- External customer portal.
- Complex RBAC beyond `operator` and `admin`.
- Online Word editing.
- Online translation editing and regenerate-from-human-edit flow.
- Batch upload.
- Task-scoped real file deletion.
- Real S3 delete rollout.
- Autonomous cleanup scheduler execute.
- Real provider cancellation.

## Verification Expected

Before release, run:

```bash
cd frontend && npm run build
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/check_release.py
```

Deployment acceptance should additionally cover:

- `/api/v1/health/live`
- `/api/v1/health/ready`
- `/api/v1/health/metrics`
- operator role smoke
- admin role smoke
- upload/create/query/download smoke with a non-sensitive PDF sample

## Files Updated In Final Packaging

- `README.md`
- `docs/runbooks/internal-portal.md`
- `frontend/src/layouts/AppLayout.vue`
- `frontend/src/router/index.ts`
- `frontend/src/components/PdfUploadPanel.vue`
- `frontend/src/components/AppBreadcrumb.vue`
- `frontend/src/pages/TemplateDetailPage.vue`
- `frontend/src/pages/SystemStatusPage.vue`
- `frontend/src/pages/OpsDashboardPage.vue`
- `frontend/src/pages/FileRetentionPage.vue`
