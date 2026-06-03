# md2word 产品成熟化路线图任务拆解

本文件是规划拆解，不代表开始实现。进入实现前需要为具体子任务创建 Trellis task，并在对应 task 内完成 PRD/design/implement 审核。

## Phase 1 Minimum Scope

### Frontend

- 信息架构
  - 主导航暴露任务工作台、配置中心、提案审核、系统状态。
  - 按角色控制 Admin-only 页面与操作。
- 任务列表
  - 状态筛选、归档筛选、轻量搜索/排序。
  - 行操作：查看、下载、失败重试、处理中取消、终态归档。
  - 批量操作：批量重试失败任务、批量归档终态任务。
- 任务详情
  - 顶部 action panel。
  - 阶段状态、失败原因、事件日志。
  - 配置快照。
  - 文件/结果区。
  - 术语/翻译术语提案入口。
- 上传/重试
  - Operator 默认配置摘要。
  - Admin 高级资源版本选择。
  - 重试时支持沿用原配置、Admin 使用最新默认配置或指定版本。
- 系统状态
  - Admin 只读页面。
  - 展示 readiness、metrics、worker、metadata store、artifact storage、默认资源状态。

### Backend

- 复用已有 `document-jobs` 操作接口。
- 补强任务列表查询参数：`q`、`sort`、`include_archived`、时间范围。
- 提供或约定任务文件汇总接口。
- 提供或约定任务创建配置摘要接口。
- 系统状态可以先由前端聚合 health endpoints；如果前端复杂度上升，再补 `GET /api/v1/system/status`。
- 提案 payload 补任务上下文字段，或先明确当前字段映射。

### Verification

- 角色验收：Operator 看不到 Admin-only 配置选择和系统管理操作。
- 状态验收：pending/queued/running/succeeded/failed/canceled/archived 在列表和详情中的操作可用性正确。
- 语义验收：归档不删除文件；取消文案不承诺强制中断外部长任务。
- 配置验收：任务详情能回看当次配置快照。
- 提案验收：从任务详情创建的提案能在审核队列识别来源任务。
- 运维验收：系统状态页只读且可解释 backend/worker/storage 状态。

## Recommended Trellis Tasks

### 1. `frontend-information-architecture`

目标：补主导航和角色化入口。

范围：
- App layout 导航。
- Admin-only 页面入口。
- 配置中心、提案审核、系统状态入口。

验收：
- Operator/Admin 登录后看到符合权限的主导航。
- 不改变后端主流程。

### 2. `document-job-workbench-completion`

目标：任务列表和详情完成日常操作闭环。

范围：
- 列表筛选、搜索、排序、归档筛选。
- 行操作和轻量批量操作。
- 详情 action panel、事件日志、失败信息。

后端依赖：
- 任务列表查询增强；若不做，前端只能基于当前分页做轻量能力。

### 3. `document-job-files-and-results`

目标：任务详情补文件/结果/日志区。

范围：
- 源文件、结果文件、debug/log 文件展示。
- 下载入口和过期/不可用状态。

后端依赖：
- 文件汇总 API 或在 job detail 中补充 file summaries。

### 4. `admin-job-configuration`

目标：创建/重试任务时支持角色化配置选择。

范围：
- Operator 默认配置摘要。
- Admin 高级选择模板、术语规则集、翻译术语集、翻译配置。
- 重试策略选择。

后端依赖：
- 配置摘要 API 或前端聚合。
- 明确显式版本字段和权限校验。

### 5. `job-context-proposals`

目标：从任务详情提交术语/翻译术语提案。

范围：
- 任务详情提案入口。
- 提案表单带任务上下文。
- 提案审核页展示来源任务回链。

后端依赖：
- 提案 payload 支持来源任务字段，或映射到现有 notes/reason 字段。

### 6. `admin-system-status`

目标：Admin 只读系统状态页。

范围：
- readiness/metrics 展示。
- worker/backend/storage/resource 状态。
- 跳转失败任务和运行中任务筛选。

后端依赖：
- 可先复用 health endpoints。
- 后续可增加系统状态聚合 API。

## Later Trellis Tasks

- `term-rule-workbench`
  - 完整术语规则 CRUD、分类、启停、导入导出、模拟、版本 diff。
- `translation-term-set-management`
  - 翻译术语集列表、详情、导入导出、版本、默认、回滚。
- `translation-result-qa`
  - 段落对照、术语命中、AI call trace、质检状态。
- `file-retention-management`
  - 文件搜索、物理删除、保留策略、清理计划、存储统计。
- `audit-log-viewer`
  - 操作审计查询、筛选、导出。
- `ops-dashboard`
  - Worker/队列监控、告警、恢复动作。
- `document-job-bulk-apis`
  - 后端批量重试、批量归档、批量取消接口。

## Explicit Non-goals For Phase 1

- 不做外部客户门户。
- 不做完整术语规则 CRUD 工作台。
- 不做物理文件删除。
- 不做独立文件管理页。
- 不做独立翻译结果页。
- 不做在线修改系统环境配置。
- 不承诺取消能强杀已经进入外部服务的长任务。
