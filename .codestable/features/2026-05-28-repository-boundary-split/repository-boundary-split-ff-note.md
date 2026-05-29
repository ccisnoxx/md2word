---
doc_type: feature-ff-note
feature: repository-boundary-split
date: 2026-05-28
requirement: fastapi-backend-productization
roadmap: backend-worker-storage-evolution
roadmap_item: repository-boundary-split
tags: [backend, jobs, repository, worker, storage]
---

# Repository Boundary Split Fastforward Note

## 做了什么

把 jobs repository 的语义边界拆成 job snapshot、job events、job files 和 stage message store 四类 port。当前仍由同一个 `FileJobRepository` 组合实现，`job.json`、`files.json`、`events.jsonl` 和 `stage_messages/*.json` 的物理格式不变。

## 改了哪些

- `app/repositories/protocols.py` 新增 `JobSnapshotRepositoryProtocol`、`JobEventRepositoryProtocol`、`JobFileRepositoryProtocol`，旧 `JobRepositoryProtocol` 保留为组合兼容协议。
- `app/services/jobs/command.py`、`query.py`、`lifecycle.py`、`stage.py` 改为依赖更窄的 repository / store port。
- `app/core/runtime.py` / `app/main.py` 显式挂载并注入 `job_repository`、`job_file_repository`、`job_event_repository` 和 `stage_message_store`。
- `tests/test_fastapi_jobs_backend.py` 同步测试运行时注入方式，继续保留 `runtime.repository` 作为兼容访问。

## 怎么验证的

- `python3 -m compileall -q app/repositories/protocols.py app/services/jobs/command.py app/services/jobs/query.py app/services/jobs/lifecycle.py app/services/jobs/stage.py app/core/runtime.py app/main.py tests/test_fastapi_jobs_backend.py`
- `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_upload_zip_dispatches_stage_through_runtime_dispatcher tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_replay_pending_replays_pending_and_running_stage_messages_only tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_retry_requeues_failed_pdf_submit_to_mineru_stage`
- `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend tests.test_job_workflow_policy tests.test_job_artifact_contract`

## 顺手发现

- `runtime.repository` 仍保留为对测试和少量兼容路径的统一 file repository 访问口；后续如果要继续收紧，可以逐步把内部读写迁到显式 port 字段。
