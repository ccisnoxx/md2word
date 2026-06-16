# md2word 总计划 / 集成计划：任务处置中心与契约防漂移

## 业务目标

本轮按两轮推进：

1. 第一轮交付“失败/停滞任务处置中心”，让 operator/admin 在任务列表和详情页中能直接判断任务卡在哪里、失败原因是什么、能执行哪些动作、下一步应该怎么处理。
2. 第二轮交付“前后端契约防漂移”，让 `Files + Document Jobs` 的 OpenAPI、前端类型、API client、mock、release check 保持一致，避免旧 `/api/v1/jobs`、手写类型和 smoke mock 漂移。

本轮不把 Word 交付质量列为 P0，不改 Word renderer、DocumentIR 质量、Golden Sample 扩容或外部调试项目。若后续出现明确当前回归，再单独进入 Word 交付专项。

## API Contract

- 公开用户链路只使用：
  - `POST /api/v1/files/upload-url`
  - `PUT /api/v1/files/{file_id}/content`
  - `POST /api/v1/document-jobs`
  - `GET /api/v1/document-jobs`
  - `GET /api/v1/document-jobs/{job_id}`
  - `GET /api/v1/document-jobs/{job_id}/events`
  - `GET /api/v1/document-jobs/{job_id}/files`
  - `GET /api/v1/document-jobs/{job_id}/callback-summary`
  - `GET /api/v1/document-jobs/{job_id}/download-url`
  - `POST /api/v1/document-jobs/{job_id}/retry`
  - `POST /api/v1/document-jobs/{job_id}/clone`
  - `POST /api/v1/document-jobs/{job_id}/cancel`
  - `DELETE /api/v1/document-jobs/{job_id}`
  - `POST /api/v1/document-jobs/{job_id}/unarchive`
- 不恢复、不扩展公开 `/api/v1/jobs`；旧 jobs 只作为历史或内部遗留说明。
- `DocumentJobResponse.available_actions` 是前端动作启用、禁用和原因展示的唯一业务真源。
- 任务处置展示优先复用现有字段：`status`、`stage`、`progress`、`failed_stage`、`error_code`、`error_message`、`updated_at`、`available_actions`、events、files、callback summary。
- 如后端新增 diagnosis 投影，只能是只读 projection，不改变任务状态机，不引入第二套任务状态。
- 结构化错误合同：
  - 前端优先读取 `error.code`、`error.message`、`error.trace_id`。
  - 兼容 legacy `error_code`、`detail`、`trace_id`。
  - `403` 表示权限不足，`409` 表示状态冲突，`503` 表示运行时能力未就绪。

## 数据模型 / 状态流

- `document_jobs.status` 保持：`pending | queued | running | succeeded | failed | canceled`。
- `document_jobs.stage` 保持：`uploaded | parsing | parsed | ir_converting | rendering | uploading | completed | failed | canceled`。
- 活跃态：`pending/queued/running`；终态：`succeeded/failed/canceled`；归档由 `archived_at` 正交表达。
- 任务处置状态由当前 job record、events、callback message summary、file metadata 派生；不新增用户可写状态。
- 停滞判断用于提示和排障，不自动改变 job 状态；自动重试、真实 provider cancel、多 worker claim 不进入本轮。
- 文件可用性由 Files metadata 和 `available_actions` 共同表达；不做 task-scoped 文件删除，不打开真实 S3 delete。

## 权限 / 错误模型

- operator：
  - 能查看和处理自己有权限的 document job。
  - 能下载自己任务的允许文件。
  - 只能看到自己任务的失败诊断和 trace id。
- admin：
  - 能进入系统状态、Ops、文件保留、跨任务诊断视图。
  - 高风险动作仍必须 preview、reason、confirmation、audit。
- 任务动作权限由后端命令接口最终校验；前端禁用态只是展示。
- 所有用户可见错误必须展示 message/code/status/trace id，并支持复制诊断信息。
- 错误消息不得泄露 token、签名 URL、私有路径或上游密钥。

## 后端范围

- Schema：
  - 保持 `DocumentJobResponse` 兼容。
  - 必须确保 list/detail/command response 都包含完整 `available_actions`。
  - 如新增 diagnosis projection，应进入 Pydantic schema 和 OpenAPI。
- Migration：
  - 第一轮不做 DB migration。
  - 第二轮不强制迁移；若未来做热查询索引、多 worker 原子 claim、artifact reconciliation，再另立专项。
- Service/API：
  - `DocumentJobService` 负责汇总任务处置所需只读信息。
  - Router 只做鉴权、参数、HTTP 错误映射和 response 包装。
  - 不把诊断逻辑散落到前端硬编码规则里。
- 异步任务：
  - 不改 MinerU、DocumentIR、Word renderer。
  - 保证 not-ready、callback replay、timeout/stale 的事件和 health/metrics 能被页面消费。
- 文件处理 / 存储：
  - 继续通过 Files API 和 download-url 访问 artifact。
  - 不做物理删除能力扩展。
  - storage metadata 不一致、orphan object 扫描列为后续可靠性专项。

## 前端范围

- 页面：
  - `JobsPage` 增强失败摘要、停滞提示、行级 pending、防重复点击和批量动作反馈。
  - `JobDetailPage` 首屏增加“任务处置面板”，集中展示阶段、失败、trace、callback、文件和推荐下一步。
  - `SystemStatusPage`/Ops 只链接到已有只读或 gated 能力，不新增危险执行入口。
- 组件：
  - `JobActions` 必须显式展示每个动作的 `disabled_reason`。
  - `ApiErrorAlert` 继续统一展示 code/status/trace id 和复制诊断。
- 状态管理：
  - 不新增大型全局 store。
  - 使用页面局部状态或小 composable 管理 refresh、pending、diagnosis display、empty/loading/error。
- API client / 类型：
  - `documentJobsApi` 只访问 `/api/v1/document-jobs`。
  - `types.ts` 与 OpenAPI 核心字段对齐。
  - smoke mock 必须覆盖 `available_actions`、失败字段、callback summary、files 和结构化错误。
- Loading / error / empty states：
  - 区分初次 loading、后台刷新、局部 events/files/callback 失败、filtered empty、无失败任务、任务不可重试、runtime 503。

## Mock 或 Contract First

- 合同权威顺序：后端 Pydantic schema -> OpenAPI snapshot -> `docs/api/*.md` -> 前端 API type/client -> smoke mock。
- 第二轮必须补 contract check：
  - `/api/v1/jobs` 不得重新出现在 OpenAPI。
  - document-jobs 核心字段不得从 OpenAPI、前端类型或 mock 中缺失。
  - `available_actions` 的 action key、enabled、disabled_reason 必须可被 mock 和 smoke 覆盖。
- mock 场景至少包含：
  - active job
  - stale running job
  - failed retryable job
  - failed non-retryable job
  - canceled/archived job
  - 403/409/503 structured error
  - callback pending/failed summary

## 端到端验收

- Operator 从任务列表进入失败任务详情，不看后端日志也能知道失败阶段、错误码、trace id 和下一步动作。
- Running 任务超过停滞阈值时，列表和详情均给出明确提示，但不自动改变状态。
- 所有动作按钮的可用性和禁用原因与后端 `available_actions` 一致。
- API contract check 能在核心字段漂移、旧 `/api/v1/jobs` 回流、mock 缺少任务处置字段时失败。
- `/ready` 的 P0 blocker 仍作为发布门禁；`/live` 不被解释为可发布。

## 风险、回滚点、验证命令

- 风险：前端推荐动作过度推断。回滚点：仅展示后端字段和 `available_actions`，移除推荐文案。
- 风险：diagnosis projection 与已有字段重复。回滚点：不新增 projection，前端只聚合现有 response。
- 风险：contract check 误报阻塞发布。回滚点：先降级为 warning，但保留 OpenAPI snapshot 和旧 jobs 禁止检查。
- 风险：多 worker 并发语义被误认为已生产化。回滚点：在文档、ready 和运维说明中继续声明单 worker/低并发边界。

验证命令：

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_openapi_export
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/check_release.py
cd frontend && npm run test:unit
cd frontend && npm run build
cd frontend && npm run test:smoke
```
