# Trellis Task Breakdown Draft

## Parent Task

- `06-09-md2word-product-maturity-roadmap`
- Purpose: 产品成熟度路线图、PRD、页面清单、API / 数据模型清单和子任务边界。
- Status: planning only.

## Candidate Child Tasks

Confirmed priority order:

1. `document-job-workbench-closure`
2. `translation-qa-review-loop`
3. `config-governance-ux-consolidation`
4. `file-library-retention-ux-split`
5. `product-navigation-and-role-model` as a cross-cutting follow-up if not absorbed by earlier phases.

### 1. `document-job-workbench-closure`

Goal: 收口任务工作台日常交付闭环。

Scope:

- `/jobs` 增强：批量取消、创建时间筛选、失败 / 运行中快捷视图、已归档视图提示。
- `/jobs/:jobId` 增强：详情分区、事件流筛选、文件下载和失败诊断清晰化。
- 评估是否需要后端 `available_actions` / `disabled_reasons`。

Acceptance:

- operator 不需要进入系统状态页，也能完成日常任务交付处理。
- admin 能批量处理失败 / 运行中任务。
- 前端不重复实现复杂业务规则；必要规则以后端合同为准。

### 2. `translation-qa-review-loop`

Goal: 建立翻译 QA 队列和复核闭环。

Scope:

- 新增或增强 QA 队列入口。
- 先复用现有 `/document-jobs?translation_qa_status=...` 和 `/translation-qa` 接口，不提前新增专用 queue API。
- 从 QA 问题跳转到翻译术语 proposal。
- 页面落地后基于统计、性能或字段缺口再评估是否需要 QA summary 聚合接口。

Acceptance:

- reviewer 能找到未复核任务。
- reviewer 能基于证据保存 QA 状态和问题归因。
- 术语问题进入 proposal，不直接改 production terms。

### 3. `config-governance-ux-consolidation`

Goal: 让配置中心从“页面很多”变成“治理链路清楚”。

Scope:

- 重新梳理 `/settings` 信息架构。
- 统一配置二级页返回上级体验：从 `/settings/templates`、`/settings/term-rule-sets`、`/settings/term-rules`、`/settings/translation-profiles`、`/settings/translation-term-sets` 能明确返回 `/settings`。
- 将术语规则逻辑入口合并为“术语工作台”，保留 `当前生效规则` 和 `草稿与发布` 两个子视图 / tabs。
- 明确 Term Rule Set draft edit 是生产修改入口。
- 明确 live Term Rules Workbench 是检查 / 模拟入口。
- 优化 diff/preflight/proposal/publish 的文案和入口。

Acceptance:

- admin 明确知道 draft、published、default、runtime live 的区别。
- publish 前能看到风险和 proposal 关联。
- operator 只能提交 proposal 或查看，不误触生产配置。

### 4. `file-library-retention-ux-split`

Goal: 拆解当前过重的文件保留页。

Scope:

- `文件库` 视图：只读搜索、定位文件、跳转任务。
- `容量与策略` 视图：storage usage、quota dry-run、quota ops summary、retention policies。
- `清理执行` 视图：mark-expired、delete-preview、delete-expired、cleanup run、history。
- 保留 preview、reason、confirmation phrase、audit 的安全链路。

Acceptance:

- admin 能定位文件和任务。
- 容量问题与清理动作分离。
- 危险操作不弱化后端安全合同。

### 5. `backend-contract-gap-analysis`

Goal: 系统性确认前端产品化需要的少量后端补洞。

Scope:

- 设计并补齐已确认的 `DocumentJobResponse.available_actions` / `disabled_reason` 合同。
- 设计并补齐已确认的 `unarchive` 元数据操作。
- 设计并补齐已确认的 `clone/rerun as new job` 操作，与 `retry` 语义分离。
- QA queue summary / mode filter 暂缓，等待 `/translation-qa` 视图验证真实缺口。
- 明确不做 task-scoped file deletion；真实删除继续只走文件库 / retention / cleanup 执行链路。

Acceptance:

- 每个缺口都有“做 / 不做 / 暂缓”决定。
- 做的缺口有 API 合同草案和验收标准。
- 不做的缺口有产品理由。

### 6. `product-navigation-and-role-model`

Goal: 统一导航和角色体验。

Scope:

- 一级导航：任务、QA、配置、系统。
- 二级导航：配置和系统子页面统一 breadcrumb / 返回上级模式。
- 详情页导航：列表 -> 详情 -> 关联详情时，保留稳定返回路径，避免只能依赖浏览器历史。
- operator/admin 可见性和禁用原因。
- 页面入口命名和信息架构。

Acceptance:

- 用户按角色能找到该做的事。
- admin-only 页面和动作有清晰边界。
- 不引入复杂 RBAC 系统。

## Deferred Tasks

- `batch-upload-workflow`
- `external-customer-portal`
- `online-word-review-editor`
- `translation-result-diff-and-scoring`
- `prompt-body-editor`
- `full-rbac-admin`

这些任务不建议进入近期路线图，除非产品边界从内部工作台转向外部服务平台。
