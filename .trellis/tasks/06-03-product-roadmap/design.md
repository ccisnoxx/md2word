# md2word 产品成熟化路线图设计

## Current State

后端 `document-jobs` 已提供创建、列表、详情、事件、重试、取消、归档、下载等核心 API。文件服务已提供上传授权、上传内容、文件元数据查询。模板、术语规则集、翻译配置、提案审核、健康检查已有不同程度的后端能力。

前端已有任务列表、任务详情、上传面板、配置中心、模板管理、术语规则集、翻译配置、提案审核页面。主要差距不是主流程不可用，而是内部工作台的信息架构和操作闭环不完整：部分页面未进入主导航，任务取消/归档等已有 API 没有完整暴露，任务详情缺少文件/结果/提案入口，Admin/Operator 的配置权限边界还没有产品化。

## Multi-role Conclusions

### Product

第一阶段服务内部 Operator/Admin，而不是外部客户门户。核心场景是“批量处理 PDF 文档，并在失败或质量问题出现时能追踪、重试、沉淀术语规则”。MVP 后最值得补齐的是任务生命周期操作、任务详情可追溯性、上下文提案和轻量运维状态。

暂不做完整术语规则 CRUD 工作台、独立文件管理、独立翻译结果质检、外部租户门户、真实物理删除和复杂运维控制。

### Frontend

前端优先补完整任务工作台，而不是扩大配置平台。关键动作是补主导航、任务列表批量操作、任务详情 action panel、文件/结果区、事件日志可读性、任务上下文提案入口、Admin 配置选择面板、Admin 只读系统状态页。

现有配置中心、提案审核页应进入信息架构，但第一阶段不要求把术语规则编辑做成完整工作台。

### Backend

第一阶段应尽量复用已有 `document-jobs`、`files`、`term proposals`、`translation term proposals`、`templates`、`term-rule-sets`、`translation-profiles`、`health` API。

需要补强的后端能力集中在查询体验和前端聚合：任务列表搜索/排序/归档筛选、任务配置摘要、任务上下文提案字段、文件/结果元数据、可选的配置摘要聚合 API、系统状态聚合 API。批量操作可以先前端逐个调用单任务 API，后续再做 bulk endpoint。

### UX

用户不应被迫理解后端资源版本模型。Operator 看默认配置摘要，Admin 在高级区显式选择版本。取消、归档、删除必须文案清楚：归档不是删除，取消不保证杀掉已进入外部系统的长耗时阶段。

任务详情是工作台的核心信息面板，应把状态、配置、日志、文件和提案入口放到一个上下文里，减少跨页面跳转。

### QA / Ops

验收重点是状态流转、终态操作、失败重试、权限边界、事件日志、配置快照和文件结果可追溯性。第一阶段不引入危险运维按钮，降低误删、误停、误改配置的风险。

## Product Roadmap

### Phase 1: Task Workbench Completion

目标：内部 Operator/Admin 可以围绕一个文档任务完成日常处理闭环。

范围：
- 任务列表补状态筛选、轻量搜索/排序、终态归档、失败重试、处理中取消、轻量批量操作。
- 任务详情补 action panel、事件日志、失败信息、配置快照、文件/结果区、提案入口。
- 上传/重试补角色化配置摘要和 Admin 高级选择。
- 主导航暴露任务、配置、提案、系统状态。
- Admin 只读系统状态页。

### Phase 2: Configuration Governance

目标：让 Admin 能稳定治理模板、术语、翻译配置。

范围：
- 完整术语规则工作台：新增、修改、启停、删除、分类、优先级、导入导出、规则模拟。
- 术语规则集 diff、发布前校验、冲突提示。
- 翻译术语集管理页面：导入、导出、版本、默认、禁用、回滚。
- 提案队列增强：批量审核、冲突解决、从任务上下文回链。

### Phase 3: Result QA and Traceability

目标：让翻译质量、术语命中和结果验证可追踪。

范围：
- 翻译结果/质检页。
- 段落对照、术语命中 trace、AI call log 可视化。
- debug archive 下载和诊断入口。
- 任务级质量标记、复核状态、问题归因。

### Phase 4: Operations and Retention

目标：补齐内部运维和数据生命周期。

范围：
- 文件管理和保留策略。
- 物理删除、清理计划、存储空间统计。
- 操作审计查询。
- Worker/队列监控和告警。
- 更完整的任务恢复与外部服务取消。

## Page Inventory

### Existing Pages To Strengthen

- `JobsPage`
  - 补轻量搜索/排序/归档筛选。
  - 补批量选择、批量归档、批量重试。
  - 补取消、归档操作入口。
  - 状态文案区分 queued/running/failed/canceled/archived。
- `JobDetailPage`
  - 补顶部 action panel：下载、重试、取消、归档、刷新。
  - 补文件/结果区：源 PDF、生成 Word、日志/debug 入口、文件状态。
  - 补配置快照展示：模板、术语规则集、翻译术语集、翻译配置。
  - 补任务上下文提案入口。
  - 强化事件日志和失败原因可读性。
- `PdfUploadPanel`
  - Operator 展示默认配置摘要。
  - Admin 展示高级配置选择。
  - 按 health/配置 readiness 提示 en2zh 可用性。
- `SettingsHomePage`
  - 作为配置中心入口保留。
  - 第一阶段只暴露已有模板、术语规则集、翻译配置入口，不扩成完整规则 CRUD。
- `TermProposalsPage`
  - 进入主导航。
  - 支持从任务详情带上下文创建的提案回链。
- `TemplateListPage` / `TemplateDetailPage`
  - 第一阶段只修补和任务配置选择相关的信息展示，不扩大模板治理范围。
- `TermRuleSetPage`
  - 第一阶段保留现有规则集版本治理，不做完整 CRUD。
- `TranslationProfilesPage`
  - 第一阶段保留现有配置管理，不做高级 prompt 工作台。

### New Pages

- `SystemStatusPage`
  - Admin 可见。
  - 只读展示 readiness、metrics、worker/backend/storage/resource 状态。
  - 链接到失败任务和运行中任务筛选。

### Deferred Pages

- `TermRuleWorkbenchPage`
- `TranslationTermSetPage`
- `FileManagementPage`
- `TranslationResultQaPage`
- `AuditLogPage`
- `OpsDashboardPage`

## Backend API Plan

### Reuse Existing APIs

- `POST /api/v1/document-jobs`
- `GET /api/v1/document-jobs`
- `GET /api/v1/document-jobs/{job_id}`
- `GET /api/v1/document-jobs/{job_id}/events`
- `POST /api/v1/document-jobs/{job_id}/retry`
- `POST /api/v1/document-jobs/{job_id}/cancel`
- `DELETE /api/v1/document-jobs/{job_id}`
- `GET /api/v1/document-jobs/{job_id}/download-url`
- `POST /api/v1/files/upload-url`
- `PUT /api/v1/files/{file_id}/content`
- `GET /api/v1/files/{file_id}`
- `GET /api/v1/templates`
- `GET /api/v1/templates/{template_id}`
- `GET /api/v1/term-rule-sets`
- `GET /api/v1/translation-profiles`
- `POST /api/v1/term-rule-proposals`
- `POST /api/v1/translation-term-proposals`
- `GET /api/v1/health/ready`
- `GET /api/v1/health/metrics`

### Recommended Phase 1 Additions

- `GET /api/v1/document-jobs` query enhancement
  - Add or verify support for `q`, `sort`, `include_archived`, `created_from`, `created_to`.
  - Keep backward compatibility with current status/limit/offset behavior.
- `GET /api/v1/document-jobs/{job_id}/files`
  - Return source/result/debug/log file summaries for task detail.
  - Can be a thin aggregation over existing file IDs and file metadata service.
- `GET /api/v1/document-jobs/config-summary`
  - Return current default template, term rule set, translation term set, translation profile and readiness.
  - Used by upload page for Operator read-only summary.
- `GET /api/v1/system/status`
  - Optional aggregation over existing health endpoints.
  - Can be deferred if frontend directly calls `/health/ready` and `/health/metrics`.
- Proposal create payload extension or convention
  - Include `source_job_id`, `source_file_id`, `source_page`, `source_text`, `reason`, `observed_version`.
  - If current proposal models already support some fields, fill only available fields in Phase 1 and document gaps.

### Deferred API Additions

- `POST /api/v1/document-jobs/bulk-retry`
- `POST /api/v1/document-jobs/bulk-archive`
- `GET /api/v1/audit-events`
- `GET /api/v1/files`
- `DELETE /api/v1/files/{file_id}`
- `POST /api/v1/files/retention-runs`
- Full term rule CRUD frontend-facing contract and validation helpers.
- Translation term set list/detail/default/rollback APIs if not already aligned with frontend needs.

## Data Model Plan

### Document Job

Needed fields for UI:
- `job_id`
- `status`
- `stage`
- `progress`
- `created_at`
- `updated_at`
- `started_at`
- `completed_at`
- `archived_at`
- `retry_count`
- `max_retries`
- `source_file_id`
- `result_file_id`
- `template_version_id`
- `term_rule_set_id`
- `term_rule_version_id`
- `translation_term_set_id`
- `translation_term_version_id`
- `translation_profile_id`
- `translation_profile_version_id`
- `request_snapshot`
- `failure_reason`
- `failure_stage`
- `created_by`

### Job Event

Needed fields for UI:
- `event_id`
- `job_id`
- `event_type`
- `stage`
- `message`
- `payload`
- `created_at`
- `actor`

### File Summary

Needed fields for UI:
- `file_id`
- `file_type`
- `status`
- `filename`
- `content_type`
- `size_bytes`
- `page_count`
- `created_at`
- `expires_at`
- `download_available`

### Proposal Context

Needed fields for UI:
- `proposal_id`
- `proposal_type`
- `source_job_id`
- `source_file_id`
- `source_text`
- `suggested_term`
- `suggested_rule`
- `reason`
- `observed_version`
- `status`
- `reviewer`
- `review_reason`

### System Status

Needed fields for UI:
- `readiness_status`
- `metadata_store`
- `artifact_storage`
- `worker_mode`
- `queue_status`
- `resource_defaults`
- `running_jobs_count`
- `failed_jobs_count`
- `audit_events_total`

## Phase 1 Acceptance

- Operator can create a task using default configuration, see the exact configuration summary, monitor progress, open detail, inspect events, download result, and submit a task-context proposal.
- Admin can create or retry a task with explicit resource selections, review proposals, and publish approved changes through existing governance flow.
- Failed tasks can be retried; running/queued tasks can be canceled with honest cancellation semantics; terminal tasks can be archived without deleting files.
- Task list supports practical filtering and light batch operations.
- Task detail contains enough file/result/log information for QA/Ops to diagnose common failures.
- Admin can view a read-only system status page without changing runtime settings.
