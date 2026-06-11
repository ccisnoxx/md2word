# md2word 任务控制台与契约收敛总计划

## 业务目标

第一轮交付“任务控制台与创建闭环成熟化 + 契约/维护口径收敛”：

- 让 operator 能清楚完成上传、创建、跟踪、失败处理、下载、重试、取消和归档。
- 让前后端围绕 `/api/v1/files` 与 `/api/v1/document-jobs` 收敛，避免旧 `/api/v1/jobs`、手写类型、mock 和错误体继续漂移。
- Word 交付质量保持为已稳定能力，不作为本轮 P0；仅在明确当前回归证据出现时记录为风险。

第二轮交付“发布可验收与运维可见性闭环”：

- 统一 readiness、release check、admin/ops smoke、真实外部动作 gate。
- 不默认启用真实 S3/provider/Slack/scheduler 执行动作。

## API Contract

- 主链路 API：`POST /api/v1/files/upload-url`、`PUT /api/v1/files/{file_id}/content`、`POST /api/v1/document-jobs`、`GET /api/v1/document-jobs`、`GET /api/v1/document-jobs/{job_id}`、`events/files/download-url/retry/clone/cancel/archive/unarchive`。
- 第一轮不新增强制页面级 API；任务列表和详情优先使用现有 `status`、`stage`、`progress`、`failed_stage`、`error_code`、`error_message`、`updated_at`、`available_actions`。
- 后端合同只做兼容增强：结构化错误优先、OpenAPI/type/mock 检查、创建任务 readiness gate。
- 第二轮以 `/api/v1/health/ready`、`/api/v1/health/live`、`/api/v1/ops/*` 和 release scripts 为中心，不改任务主链路。

## 数据模型 / 状态流

- `DocumentJob.status`：`pending | queued | running | succeeded | failed | canceled`。
- 活跃态：`pending/queued/running`；终态：`succeeded/failed/canceled`；归档态由 `archived_at` 正交表达。
- 前端展示可用操作必须消费后端 `available_actions`，不得按 status 自行推断命令是否可用。
- UI stale 状态只由前端本地刷新时间和 `updated_at` 推导，不落库。

## 权限 / 错误模型

- operator：只能访问自己的任务、创建任务、下载自己有权访问的结果、执行后端允许的 action。
- admin：可访问系统状态、ops、配置治理和跨用户任务视图。
- 前端错误归一化优先级：`error.code/error.message/error.trace_id` 或 `request_id` 优先；兼容 legacy `error_code/detail/trace_id`。
- 创建任务 readiness gate：当 P0 required 且 execution not ready 时，`POST /api/v1/document-jobs` 返回 `503 document_jobs_not_ready`，不生成注定卡住的 pending job。

## 后端范围

- Schema：保持 `DocumentJobResponse` 兼容；所有返回该 schema 的路径必须填充 `available_actions`。
- Migration：第一轮不做 DB migration。
- Service：创建前执行 readiness gate；抽小型 workflow/policy 收口 active/terminal/action/status-group 常量。
- API：列表保留 `status`，增加 `status_group=active` 和筛选后 summary；错误体保持结构化。
- 异步任务：不改 Word 生成链路；不做多 worker claim 重构，只记录风险。
- 文件处理 / 存储：继续使用 files/document_files 和 download-url；不执行真实 S3 delete。

## 前端范围

- 页面：创建页 readiness blocker、上传/创建状态、任务列表 active refresh/stale/failed summary、详情页轮询降噪。
- 组件：`JobActions` 显式展示 disabled reason。
- 状态管理：不新增全局 store，Jobs 页刷新状态 page-local 管理。
- API client / 类型：修错误优先级；最小 contract check 覆盖 DocumentJob/File/Config/Error/Actions。
- Loading/error/empty：创建页、列表页、详情 tabs 均分开表达 loading/error/empty。

## 测试与验收

- 后端 unit/integration：readiness gate、response projection、available_actions、权限错误、bulk partial failure。
- 前端 unit：错误归一化、readiness 文案、action disabled reason、stale 判断、failed summary。
- Smoke：operator core flow、blocker flow、failed flow、action flow；第二轮补 admin status/ops/file-retention gate。
- Mock/contract first：前端 smoke mock 必须覆盖 active job、failed job、succeeded job、readiness blocker、bulk partial failure、403、409、503 structured error。

## 回滚点

- 任务列表自动刷新可禁用，不影响后端 API。
- readiness create gate 仅在 `p0_document_jobs_required=true` 且 not ready 时生效；开发环境保持宽松。
- contract check 先作为本地/release 检查，不阻塞运行时。
- 第二轮 `/live` 保持存活检查，`/ready` 用于业务发布门禁。

