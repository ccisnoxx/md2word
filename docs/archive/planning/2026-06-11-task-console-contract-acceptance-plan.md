# md2word 联调验收计划：任务控制台与契约收敛

## 验收目标

第一轮验收证明 operator 可完成任务闭环，前后端合同可持续维护：

- 创建页能解释配置/readiness 阻断。
- 列表页能看到 active、failed、stale 和可执行动作。
- 详情页能查看事件、文件、callback 摘要并执行允许的操作。
- API、OpenAPI、前端类型、mock、文档口径一致。

第二轮验收证明 admin/ops 能安全判断系统是否可开放：

- readiness/release check 能捕获阻断。
- ops 真实外部动作默认 gate，不误执行。

## Mock / Contract First

- 前端 smoke mock 必须覆盖：
  - succeeded job
  - active job
  - failed job
  - readiness blocker
  - bulk partial failure
  - 403 forbidden
  - 409 conflict
  - 503 structured error
- Mock 字段以后端 schema/OpenAPI 为准，不从页面临时拼。
- 后端接口完成后先更新 OpenAPI，再接前端页面和 smoke。

## 后端接口完成标准

- `POST /api/v1/document-jobs`：
  - ready 时创建成功并返回 action projection。
  - unready required 时返回 `503 document_jobs_not_ready`，不创建任务。
- `GET /api/v1/document-jobs`：
  - status/status_group/QA/search/date/sort/include_archived 行为正确。
  - summary 不受分页影响。
- 所有命令：
  - 使用服务端 `available_actions` 判定。
  - 冲突返回结构化错误。
- 权限：
  - operator scope 与 admin visibility 均有测试。

## 前端接入验收顺序

1. 后端 ready/unready 和 list filters 测试通过。
2. OpenAPI snapshot 更新。
3. 前端类型和 mock 同步。
4. 创建页 blocker smoke 通过。
5. Jobs active/failed/action smoke 通过。
6. Unit/build/smoke 全部通过。

## 端到端验收场景

- Operator core：
  1. 登录。
  2. 打开任务列表。
  3. 进入创建页。
  4. 上传 PDF。
  5. 创建任务。
  6. 返回列表看到 active 状态。
  7. 进入详情查看 events/files。
  8. 成功后生成 download-url。
- Blocker：
  1. 后端 P0 required 且 worker disabled。
  2. 创建页显示 readiness blocker。
  3. 直接调用 create 返回 `document_jobs_not_ready`。
- Failed：
  1. 列表显示 failed stage/code/message。
  2. 用户可进入详情查看诊断。
  3. 若 `available_actions.retry.enabled=true`，可重试。
- Contract：
  1. `/api/v1/jobs` 不出现在公开 OpenAPI。
  2. docs/runbooks 不再把旧 jobs 作为主入口。
  3. 前端错误体优先级单测覆盖 nested 和 legacy。

## 风险与回滚点

- 自动刷新压力：只刷新 active 页，页面隐藏时暂停，必要时关闭自动刷新。
- readiness gate 误伤开发：仅在 required and not ready 时阻断。
- Contract check 误报：第一轮只覆盖核心字段，不做全量生成。
- 文档清理扩大范围：只修公开入口、开发运行、验收相关文档。
- 第二轮 health 语义变更：保持 `/live` 为存活，`/ready` 为业务门禁。

## 验证命令

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_create_rejects_unready_required_execution
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_list_supports_workbench_filters_without_running_worker
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_openapi_export
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/check_release.py
cd frontend && npm run build
cd frontend && npm run test:unit
cd frontend && npm run test:smoke
```

