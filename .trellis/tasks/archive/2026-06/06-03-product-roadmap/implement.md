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

## Phase 1 Acceptance Closeout

收口日期：2026-06-04。

结论：Phase 1 “任务工作台成熟化”可以收口。六个 Phase 1 子任务均已完成并归档到 `.trellis/tasks/archive/2026-06/`：

- `frontend-information-architecture`
- `document-job-workbench-completion`
- `document-job-files-and-results`
- `admin-job-configuration`
- `job-context-proposals`
- `admin-system-status`

已满足的 Phase 1 验收面：

- Operator/Admin 信息架构和 Admin-only 路由边界已完成。
- 任务列表和任务详情已覆盖筛选、搜索、排序、下载、失败重试、取消、归档和批量操作闭环。
- 任务详情已覆盖事件、失败信息、配置快照、文件/结果区和任务上下文提案入口。
- 上传和重试已支持 Operator 默认配置摘要、Admin 显式资源版本选择和配置快照回看。
- Admin 系统状态页已用只读 health/metrics 信息解释 backend、worker、storage、resource 状态。
- 所有 Phase 1 子任务均明确未运行 pdf-mineru 解析、翻译或 Word 生成主流程。

不阻塞 Phase 1 收口的后续项：

- `file-retention-management` 属于后续 Operations and Retention 方向，不纳入 Phase 1 完成条件；其中 metadata-only Admin 基础切片已在 2026-06-04 完成，真实删除、策略 CRUD、定时清理和完整文件库仍后置。
- `term-rule-workbench` 和 `translation-term-set-management` 属于 Phase 2 Configuration Governance，需要按治理深度继续确认完整性。
- `translation-result-qa` 属于 Phase 3 Result QA and Traceability。
- `audit-log-viewer`、`ops-dashboard`、`document-job-bulk-apis` 是 Phase 4 / 运维增强或跨阶段加速项，不改变 Phase 1 收口结论。

## Phase 2 Acceptance Closeout

收口日期：2026-06-04。

结论：当前路线图中的 Phase 2 “Configuration Governance”切片可以收口。已归档的完成任务包括：

- `term-rule-workbench`
- `term-rule-governance-phase2`
- `translation-term-set-management`
- `translation-term-set-governance-hardening`

已满足的 Phase 2 验收面：

- Term Rule Set 已覆盖 draft CRUD contract、diff、preflight、治理 UI 和 proposal 边界冲突提示。
- Translation Term Set 已覆盖 Admin 管理入口、CSV 导入/导出、版本发布、默认版本切换、rollback 和治理硬化文案/错误体验。
- 任务创建和重试时绑定资源版本的行为保持不变。
- 归档 Trellis 文档中的 Translation Term Set 完成状态已与实际实现同步。
- 所有 Phase 2 收口任务均明确未运行 pdf-mineru 解析、翻译或 Word 生成主流程。

Phase 2 明确未做、需要后续独立任务承接的能力：

- 逐条 Translation Term CRUD。
- Translation Term Set 完整 diff、冲突解决和批量审核联动工作台。
- Term Rule governance 的自动 rebase、批量审核和更复杂发布策略。
- 面向外部客户的配置治理门户。

## Phase 3 Acceptance Closeout

收口日期：2026-06-06。

结论：当前路线图中的 Phase 3 “Result QA and Traceability”切片可以收口。已归档的完成任务包括：

- `translation-result-qa`
- `translation-result-qa-gap-audit`
- `translation-qa-visibility-hardening`
- `translation-qa-segment-trace-hardening`
- `translation-qa-browser-smoke`

已满足的 Phase 3 验收面：

- 翻译结果/质检页已落到 `TranslationResultQaPage.vue`、`/jobs/:jobId/translation-qa` 路由、`GET/PATCH /api/v1/document-jobs/{job_id}/translation-qa` 和任务详情入口。
- 段落对照已基于 `document_ir` 展示最终文本片段，并在 `ai_debug_archive` 可用时补充源文/AI 译文；归档缺失、过期或无文本时会明确展示不可用原因。
- 术语命中 trace 已从 `ai_call_log` 聚合为 `term_traces`，并在 QA 页面按 `segment_id` 做 segment-first 关联展示，同时保留无 `segment_id` 的全局 trace。
- AI call log 已以 metadata-only 方式可视化，明确标注当前仅支持 call-level evidence，不伪造 segment-to-call 关联。
- debug archive 诊断入口已通过 QA 证据文件区、源文对照可用性提示和任务详情文件/结果区承接。
- 任务级 QA 状态、复核状态和问题归因已支持持久化、非敏感事件记录、任务详情摘要、Jobs 列表列展示和后端列表筛选。

Phase 3 明确未做、但不阻塞本阶段收口的能力：

- 段落级 QA 决策持久化、在线修改译文和自动评分。
- 稳定的段落到 AI call 逐条归因；当前 artifact 没有可防守的关联键，UI 已避免误导。
- 跨任务 QA 工作台和永久浏览器回归测试框架。

所有 Phase 3 收口任务均明确未运行 pdf-mineru 解析、真实翻译 provider 或 Word 生成主流程。

## Operations and Retention Slice Closeout

收口日期：2026-06-04。

`file-retention-management` 已作为 metadata-only Operations 基础切片完成：

- Admin-only `GET /api/v1/files/retention/plan`。
- Admin-only `POST /api/v1/files/retention/mark-expired`。
- Admin-only `/system-status/file-retention` 前端页面。
- API 文档和 targeted backend/frontend 验证记录。
- 明确不删除本地文件、对象存储对象、任务记录、metadata 记录或 `object_key`。

仍属于后续 Phase 4 / Operations 的能力：

- 物理文件删除。
- 保留策略 CRUD。
- 定时清理计划和后台执行器。
- 存储配额与清理建议。
- 跨任务文件搜索或完整文件管理库。
- 审计导出、告警和恢复动作的更完整运维闭环。

## Phase 4 Acceptance Closeout

收口日期：2026-06-07。

结论：当前路线图中的 Phase 4 “Operations and Retention”内部运维成熟化切片可以收口。已归档的完成任务包括：

- `file-retention-management`
- `file-retention-operations-phase4-gap-audit`
- `file-retention-physical-delete-safety-contract`
- `file-retention-policy-crud-governance`
- `file-retention-storage-usage-quota-readiness`
- `file-retention-scheduled-cleanup-readonly-plan`
- `file-retention-file-library-search-governance`
- `audit-log-export-governance`
- `ops-dashboard`
- `ops-alerting-and-recovery-readiness`
- `ops-recovery-action-governance-gap-audit`
- `ops-recovery-action-safety-registry`
- `phase4-operations-execution-gap-audit`
- `ops-alert-delivery-outbox-safety-contract`
- `ops-provider-cancellation-safety-contract`
- `file-retention-automated-cleanup-execution-contract`
- `phase4-operations-retention-closeout`

已满足的 Phase 4 验收面：

- 文件管理和保留策略已覆盖 Admin-only 文件库安全搜索、metadata retention plan/mark-expired、retention policy CRUD/governance、policy impact preview 和 API/OpenAPI 文档。
- 物理删除、清理计划和存储统计已覆盖 selected-file physical delete safety contract、readonly cleanup report、storage usage/quota readiness，以及复用 physical-delete primitive 的 cleanup run execution contract。
- 审计查询和导出已覆盖 Admin-only audit events 查询、CSV export、导出审计记录和无服务端导出文件交付边界。
- Worker/队列监控和告警已覆盖 Ops dashboard/readiness、`/health/ops-alerts`、recovery action registry、active-alert preview 和 audit-backed fake alert delivery outbox。
- 任务恢复与外部服务取消边界已覆盖 exact-target recovery action preview、risk/safety metadata、fake provider cancellation preview/fake-cancel/dedupe/audit，并明确不调用真实 provider cancellation。

执行型 Ops 闭环的安全边界：

- `alert.delivery` 仅支持 local fake outbox；Admin-only，exact alert codes，reason、confirmation、dedupe、compact audit，且不发送 Slack/email/webhook。
- `provider.cancel` 仅支持 fake cancellation；Admin-only，exact job target，reason、confirmation、dedupe、compact audit，且不调用 MinerU 或修改本地 job 状态。
- `file_retention.automated_cleanup_execute` 仅支持 Admin 手动 cleanup run；必须先 preview，execute 校验 exact `file_ids`、`max_files`、`preview_hash`、reason 和 confirmation，内部复用现有 physical-delete safety contract，S3 仍跳过。

Phase 4 明确未做、但不阻塞本阶段收口的能力：

- 真实 Slack/email/webhook 告警投递。
- 真实 provider cancellation API 集成。
- 常驻 scheduler loop、autonomous policy executor、run history、distributed lock 和 signed cleanup plan。
- 真实 S3 删除。
- 结构化 audit details / per-file durable compliance evidence。
- quota enforcement 或上传阻断。
- 新执行合同的前端操作按钮；当前后端合同、文档和 targeted tests 已足够支撑内部 Ops 收口。

所有 Phase 4 执行型任务均明确未运行 pdf-mineru 解析、真实翻译 provider、Word 生成主流程、真实外部告警服务、真实 provider cancellation、真实 S3 删除或 scheduler loop。

## Phase 2 Archived Task Inventory

盘点日期：2026-06-04。

### `term-rule-workbench`

性质：阶段性切片，不是完整 Phase 2 术语规则治理能力。

已完成范围：

- Admin-only `/settings/term-rules` 前端入口。
- 术语规则分类概览、规则筛选、只读列表、只读详情。
- 复用现有 `POST /api/v1/term-rules/simulate` 做文本模拟。
- 明确不使用 raw HTML 渲染模拟结果。

未覆盖的完整 Phase 2 能力：

- 规则新增、编辑、启停、删除。
- 规则导入、导出、同步文件入口。
- Term Rule Set 版本 diff、冲突分析、发布前校验扩展。
- 规则治理和提案审核的批量化联动。

建议：保留当前任务为“检查/模拟台已完成”，另开 `term-rule-governance-crud` 或等价任务承接完整 CRUD、diff 和发布前校验。

### `translation-term-set-management`

性质：轻量管理能力已基本成型，但仍不是完整 Phase 2 配置治理闭环。

已观察到的实现面：

- Admin-only `/settings/translation-term-sets` 前端入口和页面。
- `translationTermSetsApi` 覆盖 list/detail/draft/import/export/publish/set-default/rollback。
- 后端 `/api/v1/translation-term-sets` 已覆盖 list/detail/draft/import/export/publish/set-default/rollback。
- API 文档和 OpenAPI 已包含 Translation Term Set 管理接口。
- 测试侧已有 Translation Term Set version service、API、rollback 和 job 快照相关覆盖。

仍缺或未确认的完整 Phase 2 能力：

- 逐条术语 CRUD 仍明确不做，CSV import 是唯一批量编辑入口。
- 完整 diff、冲突解决、批量审核联动仍未覆盖。
- 归档任务文档中 PRD checkbox 仍未同步为完成，`implement.md` 仍保留 planning 口径；需要做一次文档一致性修正。

建议：把该任务视为“Translation Term Set 轻量管理已完成”；下一步先补齐归档文档的验收/验证记录，再决定是否另开 `translation-term-governance-diff` 承接 diff、冲突解决和审核联动。

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

## Remaining Future Task Candidates

- `translation-term-governance-diff`
  - Translation Term Set diff、冲突解决和批量审核联动工作台。
- `file-retention-operations-phase4`
  - 文件搜索、物理删除、保留策略 CRUD、定时清理计划、存储配额和清理建议。
- `ops-alerting-and-recovery`
  - Worker/队列告警、恢复动作、运维 runbook 联动。
- `audit-log-export`
  - 审计日志导出、长期留存和合规查询。
- `customer-portal`
  - 外部客户自助上传、下载、状态查看和权限边界。

## Explicit Non-goals For Phase 1

- 不做外部客户门户。
- 不做完整术语规则 CRUD 工作台。
- 不做物理文件删除。
- 不做独立文件管理页。
- 不做独立翻译结果页。
- 不做在线修改系统环境配置。
- 不承诺取消能强杀已经进入外部服务的长任务。
