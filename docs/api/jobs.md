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
---

# Legacy Jobs API Removed

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
