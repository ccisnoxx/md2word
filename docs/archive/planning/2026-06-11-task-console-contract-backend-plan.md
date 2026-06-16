# md2word 后端开发计划：任务控制台与契约收敛

## 业务目标

后端第一轮目标是让任务工作台获得稳定、可解释、可验收的服务端合同：

- 创建任务前由服务端确认 P0 execution readiness，避免生成注定不会执行的 pending job。
- `DocumentJobResponse`、列表 summary、`available_actions` 和错误体成为前端唯一可信合同。
- 不把 Word 渲染质量作为本轮 P0，不改现有 renderer/worker 交付策略。

## API Contract

- `POST /api/v1/document-jobs`：
  - 成功返回 `DocumentJobCreateResponse`，内部 `job.available_actions` 必须完整。
  - 若 `p0_document_jobs_required=true` 且 `p0_document_jobs_ready=false`，返回 `503`，`error_code=document_jobs_not_ready`。
- `GET /api/v1/document-jobs`：
  - 支持 `status` 或 `status_group=active`，两者不能同时传。
  - 返回 `summary`、`filtered_summary`、`translation_qa_summary`。
- `GET /api/v1/document-jobs/{job_id}` 和命令响应：
  - 返回 `available_actions`，前端只按该字段启用/禁用按钮。
- 错误合同：
  - 继续保留 legacy `error_code/detail/trace_id`。
  - 新前端优先使用 nested `error.code/error.message/error.trace_id`。

## 数据模型 / 状态流

- 不新增表，不做 migration。
- 新增或使用 `document_jobs.workflow` policy 收口：
  - `ACTIVE_DOCUMENT_JOB_STATUSES = pending/queued/running`
  - `TERMINAL_DOCUMENT_JOB_STATUSES = succeeded/failed/canceled`
  - `ARCHIVABLE_DOCUMENT_JOB_STATUSES = terminal`
  - `CANCELABLE_DOCUMENT_JOB_STATUSES = active`
  - `DOCUMENT_JOB_STATUS_GROUPS.active = active`
- `request_snapshot` 保持兼容，但不得继续扩大前端隐式依赖；后续如需展示资源摘要，应新增 typed projection。

## Service / API / Async

- Router 层在 create 前读取 `runtime.health_service.build_dependency_checks()`，只在 required and not ready 时阻断。
- `DocumentJobService` 继续负责创建、查询、命令和 response projection。
- `DocumentJobExecutionService` 继续负责 worker stage 推进；第一轮不改 MinerU、DocumentIR、Word 生成。
- 修正 callback 或其他返回 `DocumentJobResponse` 的路径，确保 `available_actions` 不缺失。
- 多 worker 原子 claim、callback running claim、storage reconciliation 放入后续可靠性专项。

## 文件处理 / 存储

- 上传授权和内容写入继续走 files API。
- 任务结果下载继续走 `download-url`，不直接暴露长期 URL。
- 第一轮不改 storage backend，不新增真实删除。
- 第二轮只做运维可见性和 dry-run/preview gate。

## 测试

- 后端测试：
  - create readiness ready/unready。
  - list `status_group=active`、非法组合、filtered summary、QA summary。
  - detail/action responses include `available_actions`。
  - operator/admin 权限。
- OpenAPI 测试：
  - `/api/v1/jobs` 不暴露。
  - document-jobs 新 query/summary 字段进入 snapshot。
- Release check：
  - 包含 document job workbench filters、response actions、download-url、readiness runtime check。

## 后端接口完成标准

- OpenAPI snapshot 与实现一致。
- 结构化错误体和 legacy 字段同时可用。
- P0 required 且 worker disabled 时，create 被服务端阻断且不创建 job/file 绑定。
- 不新增 silent fallback、不吞 trace id、不修改 Word 交付链路。

## 验证命令

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_create_rejects_unready_required_execution
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_list_supports_workbench_filters_without_running_worker
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_openapi_export
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/check_release.py
```

