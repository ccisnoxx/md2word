# Document job workbench completion 实施计划

本任务在用户确认后再执行 `task.py start`。未 start 前只允许维护规划产物。

## Checklist

1. 后端列表查询增强
   - 修改 `app/domains/document_jobs/router.py`，为 `GET /api/v1/document-jobs` 增加 `q`、`sort`、`include_archived`、`created_from`、`created_to`。
   - 修改 `app/domains/document_jobs/service.py`，扩展 `list_jobs()`，实现可见性、归档筛选、搜索、时间范围、状态筛选、排序、分页。
   - 保持 repository 协议和响应 schema 不变。

2. 后端测试
   - 在 `tests/test_fastapi_jobs_backend.py` 增加最小 API 测试，覆盖默认隐藏归档、`include_archived=true`、`q`、`sort`、创建时间范围、非法 sort。
   - 不启用 eager worker，不触发 MinerU/翻译/Word 主流程。

3. 前端 API 和 helper
   - 修改 `frontend/src/api/documentJobs.ts` 和 `frontend/src/api/types.ts`，补列表参数类型。
   - 修改 `frontend/src/utils/format.ts`，集中定义归档/取消/重试可用性 helper（如有必要）。

4. 前端列表闭环
   - 修改 `frontend/src/pages/JobsPage.vue`，增加搜索、排序、归档筛选、批量重试、批量归档。
   - 修改 `frontend/src/components/JobTable.vue`，增加选择列、取消和归档行操作、归档标记展示。
   - 使用现有 `documentJobsApi.retry/archive/cancel/createDownloadUrl`，不新增 bulk API。

5. 前端详情闭环
   - 修改 `frontend/src/components/JobActions.vue`，增加取消、归档按钮和 loading props/emits。
   - 修改 `frontend/src/pages/JobDetailPage.vue`，接入取消/归档确认、调用 API、刷新详情和事件。
   - 确认取消和归档文案符合路线图语义。

6. 验证
   - 后端：`/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend`
   - 前端：`npm run build`，工作目录 `frontend/`
   - 如后端 OpenAPI 快照因 query params 变化导致 release check 失败，本任务只记录，不顺手扩大到 release snapshot 更新，除非用户确认。

## Review Gates

- Gate 1：后端查询增强通过 targeted unittest。
- Gate 2：前端 build 通过。
- Gate 3：人工检查 UI 操作文案没有暗示真实删除或强杀外部任务。

## Rollback Points

- 后端查询增强独立于前端，可单独回退 `router.py`、`service.py` 和对应测试。
- 前端批量操作只调用现有单任务 API，可单独回退 `JobsPage.vue`/`JobTable.vue`。
- 详情 action panel 可单独回退 `JobActions.vue`/`JobDetailPage.vue`。

## Out Of Scope

- 不新增 `POST /api/v1/document-jobs/bulk-retry` 或 bulk archive API。
- 不修改任务状态机、存储字段、文件删除语义或 worker 执行逻辑。
- 不实现文件/结果区、任务上下文提案、Admin 配置选择、系统状态页、完整术语规则 CRUD。
