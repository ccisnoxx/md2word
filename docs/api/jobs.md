---
doc_type: lib-api-ref
entry: jobs
category: endpoint
status: removed
source_files:
  - app/api/v1/router.py
  - docs/api/openapi.json
summary: Legacy `/api/v1/jobs` endpoint family has been removed from the public v1 API. Use Files + Document Jobs instead.
tags: [jobs, api, legacy, removed]
last_reviewed: 2026-06-11
doc_status: superseded
last_verified_commit: null
owner: null
verification_scope: >-
  全文占位/移除用途及明确替代入口的静态核对；原 status 和说明保留，不认证旧功能或命令。依据见 ../../.trellis/tasks/11-10-documentation-evidence-governance/research/b3-preparation.md。
---

# Legacy Jobs API Removed

本页保留已移除的 legacy Jobs API 引用入口，已由 [Files API](files.md) 与 [Document Jobs API](document-jobs.md) 的正式流程替代。原 `status: removed` 和历史说明保留；不要从旧目录仍有共享文件推断旧 HTTP 入口仍然可用。

`/api/v1/jobs` is no longer exposed by the v1 API router and must not be used by the frontend workbench or new integrations.

Use the current document job flow:

```text
POST /api/v1/files/upload-url
PUT  /api/v1/files/{file_id}/content
POST /api/v1/document-jobs
GET  /api/v1/document-jobs/{job_id}
GET  /api/v1/document-jobs/{job_id}/events
GET  /api/v1/document-jobs/{job_id}/files
GET  /api/v1/document-jobs/{job_id}/download-url
```

Task actions are driven by `DocumentJobResponse.available_actions`; clients must not infer action availability from status alone.

Operational recovery and provider cancellation are available only through document-job targets under `/api/v1/ops/*`.

Historical implementation files under `app/domains/jobs/` may still exist while shared conversion internals are being separated, but they are not a supported API surface.
