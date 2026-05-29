---
doc_type: feature-ff-note
feature: artifact-storage-local-adapter
date: 2026-05-28
requirement:
tags: [backend, jobs, artifacts, storage]
---

## 做了什么
把 artifact 注册和本地下载路径解析从 `JobArtifactService` 中抽到 `LocalArtifactStorageAdapter`，保持现有 artifact file_type、alias、media、download URL 和 filename 行为不变。

## 改了哪些
- `app/services/jobs/artifact_storage.py` — 新增 `ArtifactStorageProtocol` 和 `LocalArtifactStorageAdapter`。
- `app/services/jobs/command.py`、`app/services/jobs/stage.py`、`app/services/jobs/lifecycle.py`、`app/api/v1/routers/jobs_query.py` — 注册 artifact 和解析本地下载路径改走 `artifact_storage`。
- `app/main.py`、`app/core/runtime.py`、`tests/test_fastapi_jobs_backend.py` — 运行时注入新增 `artifact_storage` 边界。
- `.codestable/roadmap/backend-worker-storage-evolution/` — 更新 roadmap 和 item 状态。

## 怎么验证的
已通过编译检查、artifact 合同测试，以及 jobs 主链 submit/retry/callback/parsed-result 转换相关目标测试。
