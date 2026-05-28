---
doc_type: feature-ff-note
feature: stage-dispatcher-port
date: 2026-05-28
requirement: fastapi-backend-productization
roadmap: backend-worker-storage-evolution
roadmap_item: stage-dispatcher-port
tags: [backend, jobs, worker, dispatch]
---

# Stage Dispatcher Port Fastforward Note

## 做了什么

把 jobs 后台 stage 调度入口抽成 `StageDispatcherProtocol`，当前默认实现仍是同进程委托 `JobStageService.dispatch_message()` / `replay_pending()`，外部行为不变。

## 改了哪些

- `app/services/jobs/dispatch.py` 新增 dispatcher protocol 和 `InProcessStageDispatcher`。
- `app/core/runtime.py` / `app/main.py` 在 runtime 中挂载 `stage_dispatcher`，启动 replay 也改走 dispatcher port。
- `app/api/v1/routers/jobs_ingest.py`、`app/api/v1/routers/mineru_callbacks.py`、`app/api/v1/routers/jobs_ops.py` 的后台任务调度改为走 `runtime.stage_dispatcher.dispatch()`。
- `tests/test_fastapi_jobs_backend.py` 增加 HTTP 创建任务经 dispatcher 调度的回归。

## 怎么验证的

- `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_upload_zip_dispatches_stage_through_runtime_dispatcher tests.test_fastapi_jobs_backend`
- `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_job_workflow_policy tests.test_job_artifact_contract`

## 顺手发现

- `.codestable/architecture/` 与 `.codestable/roadmap/mineru-online-ingestion/` 仍有 PDF 在线链路旧描述；这不属于本次 dispatcher port 范围。
