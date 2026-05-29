---
doc_type: feature-ff-note
feature: stage-message-store-contract
date: 2026-05-28
requirement: fastapi-backend-productization
roadmap: backend-worker-storage-evolution
roadmap_item: stage-message-store-contract
tags: [backend, jobs, worker, stage-message-store]
---

# Stage Message Store Contract Fastforward Note

## 做了什么

把 stage message spool 抽成 `StageMessageStoreProtocol`，并把 replay 合同显式命名为 `list_replayable_stage_messages()`。当前 `FileJobRepository` 继续作为 file-backed store，物理存储格式不变。

## 改了哪些

- `app/repositories/protocols.py` 定义 `StageMessageStoreProtocol`，旧 `StageMessageRepositoryProtocol` 保留为兼容命名。
- `app/repositories/file_job_repository.py` 增加 `list_replayable_stage_messages()`，旧 `list_pending_stage_messages()` 作为兼容 wrapper。
- `app/services/jobs/stage.py`、`app/services/jobs/lifecycle.py`、`app/api/v1/routers/jobs_ops.py` 改为通过 `stage_message_store` 处理 stage message。
- `app/core/runtime.py` / `app/main.py` 在 runtime 中挂载 `stage_message_store`。
- `tests/test_fastapi_jobs_backend.py` 更新测试运行时，并固定 pending/running 可 replay、failed 不自动 replay。

## 怎么验证的

- `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_replay_pending_replays_pending_and_running_stage_messages_only tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_upload_zip_dispatches_stage_through_runtime_dispatcher tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_retry_requeues_failed_pdf_submit_to_mineru_stage`
- `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend tests.test_job_workflow_policy tests.test_job_artifact_contract`
- `/Users/sc/miniconda3/envs/md2word/bin/python .codestable/tools/validate-yaml.py --file .codestable/roadmap/backend-worker-storage-evolution/backend-worker-storage-evolution-items.yaml --yaml-only`
- `git diff --check`

## 顺手发现

- `FileJobRepository` 暂时仍同时实现 job snapshot、events、files 和 stage message store；这正是后续 `repository-boundary-split` 的范围。
