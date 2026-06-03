# Document job workbench completion 设计

## Current State

`/api/v1/document-jobs` 已有创建、列表、详情、事件、重试、取消、归档、下载 URL 能力。后端 `DocumentJobService.list_jobs()` 当前只支持 `status`，并且默认排除 `archived_at is not None` 的任务。归档和取消已有服务逻辑、事件和审计覆盖，归档不删除文件，取消只更新任务状态。

前端已有 `JobsPage`、`JobDetailPage`、`JobTable`、`JobActions`、`JobEventTimeline`、`JobStatusBadge` 和 `documentJobsApi`。当前列表只支持状态筛选、下载、重试；详情 action panel 只支持刷新、下载、重试。`format.ts` 已经有 `isActiveJobStatus`、`isArchivableJobStatus`、`isCancelableJobStatus`，可以继续作为 UI 操作可用性的单点 helper。

## Scope

本任务只补任务列表与任务详情工作台闭环：

- 后端列表查询增强。
- 前端列表筛选、搜索、排序、归档筛选。
- 前端行操作：下载、重试、取消、归档。
- 前端轻量批量操作：逐个调用现有单任务 retry/archive API。
- 详情 action panel 增加取消、归档。

不进入这些范围：

- `document-job-files-and-results`：源文件、结果文件、debug/log 文件展示。
- `job-context-proposals`：从任务详情创建术语/翻译术语提案。
- `admin-job-configuration`：创建/重试时 Admin 高级资源选择。
- `admin-system-status`：系统状态页。
- 完整术语规则 CRUD、真实文件删除、后端 bulk API。

## Backend API Changes

### `GET /api/v1/document-jobs`

保持响应模型 `DocumentJobListResponse` 不变，只增加可选查询参数：

- `q: str | None`
  - 服务层归一化 trim 后为空则忽略。
  - 匹配字段：`job.id`、`job.source_file_id`、`request_snapshot.source_file.original_filename`、`job.error_code`、`job.error_message`。
  - 大小写不敏感。
- `sort: str`
  - 支持枚举：`created_at_desc`、`created_at_asc`、`updated_at_desc`、`updated_at_asc`。
  - 默认 `created_at_desc`，与现有倒序体验一致。
  - 非法值返回 400 `invalid_request`。
- `include_archived: bool`
  - 默认 `false`，保持现有默认隐藏归档任务。
  - `true` 时不按 `archived_at` 排除。
- `created_from: datetime | None`
  - 包含边界，按 `job.created_at >= created_from`。
- `created_to: datetime | None`
  - 包含边界，按 `job.created_at <= created_to`。

`summary` 继续统计当前可见归档范围内、但未套用 `status/q/created_*` 后的状态分布。这样它保持“当前归档视图的状态概览”，避免随着搜索词波动。

## Backend Files

- `app/domains/document_jobs/router.py`
  - 为列表 endpoint 增加 query params 并传入 service。
- `app/domains/document_jobs/service.py`
  - 扩展 `list_jobs()` 参数。
  - 增加小型私有 helper 处理搜索、时间范围和排序校验。
  - 不改 repository 协议，不新增持久化字段。
- `tests/test_fastapi_jobs_backend.py`
  - 增加针对 document_jobs 列表查询增强的 API 测试。

## Frontend Page Changes

### `JobsPage`

- 工具栏增加：
  - 搜索框。
  - 排序下拉。
  - 是否包含归档任务开关。
  - 批量重试、批量归档按钮。
- 列表加载把 `q`、`sort`、`include_archived` 传给 `documentJobsApi.list()`。
- 批量操作在前端筛选选中任务：
  - retry：`status === "failed"` 且未归档。
  - archive：`status in succeeded/failed/canceled` 且未归档。
- 批量操作逐个调用现有 API，收集成功/失败数量，最后刷新列表。

### `JobTable`

- 增加 selection column。
- 增加取消、归档行操作。
- 已归档任务显示只读归档标记或归档时间。
- 通过 emits 把选择、取消、归档交给页面处理。

### `JobDetailPage`

- 详情顶部 `JobActions` 增加取消、归档。
- 取消/归档成功后刷新详情和事件。
- 失败重试逻辑保持现状。

### `JobActions`

- 增加取消、归档按钮和 loading props。
- 操作可用性基于 shared format helpers，不在组件内重复定义状态规则。

### `documentJobsApi` / `types.ts` / `format.ts`

- API list params 增加 `q`、`sort`、`include_archived`、`created_from`、`created_to`。
- TS 类型不引入 `archived` 任务状态；归档继续由 `archived_at` 表达。
- `format.ts` 如需补 helper，应围绕 `DocumentJobResponse` 的 `archived_at` 做单点判断，避免页面重复判断。

## Data Flow

列表页 filter state -> `documentJobsApi.list(params)` -> `GET /api/v1/document-jobs` -> `DocumentJobService.list_jobs()` -> repository list -> visibility/archive/search/date/status/sort/page -> existing response shape -> `JobTable` render。

取消/归档/重试流程都走现有单任务 API。前端批量操作只是 orchestration，不改变后端状态机和审计事件。

## Tradeoffs

- 不新增后端 bulk endpoint：减少 API surface 和状态机风险；第一阶段任务量通常可接受前端逐个调用。
- 不把归档建模为 `status=archived`：保留现有状态机，避免破坏终态语义和已有测试。
- 后端仍在 service 层加载后过滤：当前 repository port 只提供 `list_document_jobs()`，三种存储后端都能复用；后续规模上升再下推查询。

## Compatibility

- 现有 `status/page/page_size` 请求兼容。
- 默认不传新参数时列表行为保持：隐藏归档、创建时间倒序。
- 响应 schema 不变，OpenAPI 仅新增 query params。

## Risks

- 前端逐个批量操作可能部分成功，需要 UI 明确提示成功/失败数量并刷新当前列表。
- 搜索字段来自 `request_snapshot`，旧任务可能缺少 `source_file.original_filename`，helper 必须容忍缺失。
- `include_archived=true` 不等于真实删除或恢复任务，文案必须避免误导。

