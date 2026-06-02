---
doc_type: technical-plan
slug: frontend-v2-config-management-implementation-plan
component: frontend-config-management
status: current
summary: 前端 V2 配置版本管理实施计划，覆盖技术栈、路由、组件、状态、API、权限、阶段拆分和验收方式。
tags: [frontend, implementation, v2, vue, element-plus, config-management]
last_reviewed: 2026-06-01
---

# 前端 V2 配置版本管理实施计划

> 本文是 V2.1 的实施计划。它建立在 V1 任务工作台已完成的事实之上，重点补齐配置版本管理、术语 proposal 审核和最小后端追溯合同。

## 1. 实施目标

V2.1 的目标是让内部 admin 和 operator 通过前端完成以下闭环：

- Template Profile：上传 draft、创建验证任务、保存验证证据、发布、设默认。
- Term Rule Set：operator 提交 proposal，admin 审核并合并 draft，admin 发布规则集。
- Translation Profile：admin 编辑基础字段 draft，发布和回滚。
- 配置中心：展示配置发布相关待办。

## 2. 技术栈建议

沿用现有前端技术栈：

| 层级 | 选择 | 说明 |
|---|---|---|
| 构建工具 | Vite | 已在 `frontend/` 使用 |
| 框架 | Vue 3 | 继续使用 Composition API |
| 语言 | TypeScript | API 合同和组件 props 类型化 |
| UI 组件 | Element Plus | 适合内部后台和表单 |
| 状态管理 | Pinia | 继续保存 auth 和当前用户 |
| 路由 | Vue Router | 静态路由 |
| HTTP client | Axios | 复用现有 `api/client.ts` |
| 图标 | Element Plus Icons | 复用现有依赖 |

不引入：

- 动态菜单系统。
- 复杂 RBAC 前端框架。
- TanStack Query。
- Monaco。
- Prompt 编辑器。

## 3. 路由设计

新增路由建议：

| 路由 | 页面组件 | 鉴权 | 说明 |
|---|---|---|---|
| `/settings` | `SettingsHomePage` | 是 | 配置中心首页 |
| `/settings/templates` | `TemplateListPage` | 是 | Template Profile 列表 |
| `/settings/templates/:templateId` | `TemplateDetailPage` | 是 | Template Profile 版本管理 |
| `/settings/term-rule-sets` | `TermRuleSetPage` | 是 | 规则集 draft 和发布 |
| `/settings/translation-profiles` | `TranslationProfilesPage` | 是 | 翻译配置版本管理 |
| `/term-proposals` | `TermProposalsPage` | 是 | 术语建议提交和审核 |

保留现有路由：

- `/login`
- `/jobs`
- `/jobs/:jobId`

路由守卫：

- 继续按现有 auth store 校验 token。
- 未登录访问新增路由时跳转 `/login`。
- 403 在页面内展示，不自动退出。

## 4. 页面结构

### 4.1 AppLayout

新增静态导航：

- 任务工作台。
- 配置中心。
- 术语建议。

导航展示规则：

- operator 和 admin 都可见。
- admin-only 操作不靠隐藏路由保护，路由可进入但按钮和后端权限都要控制。

### 4.2 SettingsHomePage

模块：

- 配置发布待办汇总。
- Template Profile 入口。
- Term Rule Set 入口。
- Translation Profile 入口。

待办汇总只展示配置相关事项：

- 待审核 proposal 数。
- 已 approve 但未发布 proposal 数。
- 待验证/待发布 template draft 数。
- Translation Profile 未发布 draft 提示。

### 4.3 TemplateDetailPage

模块：

- 模板基础信息。
- 当前默认版本。
- 版本表格。
- 上传 draft version。
- 创建验证任务入口。
- 验证证据展示和填写。
- publish / set-default / disable 操作。

关键交互：

- publish 前弹窗要求验证任务 ID、验证说明、发布原因。
- set-default 前弹窗要求切换原因。
- publish 和 set-default 拆成两个按钮。
- operator 只看到查看和下载，不看到写操作。

### 4.4 TermProposalsPage

按角色默认视图：

- operator 默认：我的建议 + 新建建议。
- admin 默认：待审核队列。

tabs/filter：

- 待审核。
- 全部 proposal。
- 我的 proposal。
- 新建 proposal。

审核页展示：

- operator 原始建议。
- 当前目标规则。
- 提交时目标规则快照。
- 冲突提示。
- admin 最终合并内容。

### 4.5 TermRuleSetPage

模块：

- 规则集基本信息。
- default version。
- published versions。
- draft 摘要。
- 已 approve 未发布 proposals。
- publish 弹窗。
- rollback / set-default 操作。
- admin YAML 高级编辑兜底。

V2.1 暂不做完整 draft-vs-default diff。

### 4.6 TranslationProfilesPage

模块：

- profile 列表。
- profile 详情。
- draft 基础字段表单。
- published versions。
- publish / set-default / rollback。

字段：

- `target_language`
- `domain`
- `prompt_version`
- `model`
- `max_pages_per_batch`
- `max_chars_per_batch`

## 5. 组件拆分建议

| 组件 | 职责 |
|---|---|
| `RoleGate` | 根据 `user.role` 控制操作可见性 |
| `SettingsNavCards` | 配置中心资源入口 |
| `ConfigTodoSummary` | 配置待办汇总 |
| `TemplateVersionTable` | 模板版本列表 |
| `TemplateVersionActions` | publish、set-default、disable |
| `TemplateVerificationDialog` | 验证任务 ID、验证说明、发布原因 |
| `CreateTemplateValidationJobDialog` | admin 指定版本创建验证任务 |
| `TermProposalForm` | operator proposal 表单 |
| `TermSegmentEditor` | 有序分段编辑器 |
| `TermPreview` | plain/subscript/superscript 实时预览 |
| `TermProposalTable` | proposal 列表 |
| `TermProposalReviewPanel` | admin 审核详情 |
| `TermRulePicker` | 编辑/禁用 proposal 选择目标规则 |
| `TermRuleSetDraftPanel` | draft 摘要和发布 |
| `TranslationProfileDraftForm` | 翻译配置基础字段表单 |
| `DangerConfirmDialog` | 高风险操作二次确认 |

## 6. 状态管理方案

### 6.1 Pinia

继续只保存全局登录态：

- `token`
- `user`
- `isAuthenticated`
- `login()`
- `logout()`
- `loadCurrentUser()`

不把配置资源放入全局 store，避免缓存和刷新一致性问题。

### 6.2 页面局部状态

- Template 版本列表、上传状态、验证弹窗状态：页面局部 state。
- Term proposal 列表、筛选、审核详情：页面局部 state。
- Translation Profile draft 表单：页面局部 state。
- 待办汇总：Settings 首页局部 state。

### 6.3 服务端数据刷新

V2.1 使用显式刷新：

- 操作成功后刷新当前页面数据。
- 不做全局实时轮询。
- 不做 optimistic update，避免审核和发布状态被误展示。

## 7. API 对接清单

### 7.1 现有 API

Template：

- `GET /api/v1/templates`
- `GET /api/v1/templates/{template_id}`
- `GET /api/v1/templates/{template_id}/download`
- `GET /api/v1/templates/{template_id}/versions`
- `POST /api/v1/templates/{template_id}/versions`
- `POST /api/v1/templates/{template_id}/versions/{version}/publish`
- `POST /api/v1/templates/{template_id}/versions/{version}/set-default`
- `POST /api/v1/templates/{template_id}/versions/{version}/disable`

Term rules：

- `GET /api/v1/term-rule-categories`
- `GET /api/v1/term-rules`
- `GET /api/v1/term-rules/{rule_id}`
- `POST /api/v1/term-rules/simulate`
- `GET /api/v1/term-rule-sets`
- `GET /api/v1/term-rule-sets/{set_id}`
- `GET /api/v1/term-rule-sets/{set_id}/draft`
- `PUT /api/v1/term-rule-sets/{set_id}/draft/rules`
- `POST /api/v1/term-rule-sets/{set_id}/publish`
- `POST /api/v1/term-rule-sets/{set_id}/versions/{version}/set-default`
- `POST /api/v1/term-rule-sets/{set_id}/rollback`

Translation profiles：

- `GET /api/v1/translation-profiles`
- `GET /api/v1/translation-profiles/{profile_id}`
- `GET /api/v1/translation-profiles/{profile_id}/draft`
- `PUT /api/v1/translation-profiles/{profile_id}/draft`
- `POST /api/v1/translation-profiles/{profile_id}/publish`
- `POST /api/v1/translation-profiles/{profile_id}/versions/{version}/set-default`
- `POST /api/v1/translation-profiles/{profile_id}/rollback`

Document jobs：

- `POST /api/v1/document-jobs`
- `GET /api/v1/document-jobs/{job_id}`

### 7.2 必须新增或调整的后端合同

Template Version：

- publish 请求新增必填 `publish_reason`。
- set-default 请求新增必填 `set_default_reason`。
- publish 或验证证据接口支持保存：
  - `verification_job_id`
  - `verification_note`
  - `verified_by`
  - `verified_at`
- 返回的 `TemplateVersionResponse` 带出验证证据。

Term Rule Proposal：

- `POST /api/v1/term-rule-proposals`
- `GET /api/v1/term-rule-proposals`
- `GET /api/v1/term-rule-proposals/{proposal_id}`
- `POST /api/v1/term-rule-proposals/{proposal_id}/approve`
- `POST /api/v1/term-rule-proposals/{proposal_id}/reject`

proposal 最小字段：

- `id`
- `intent`: `create`、`update`、`disable`
- `status`: `pending_review`、`approved`、`rejected`
- `source_term`
- `category_id`
- `segments`
- `reason`
- `source_job_id`
- `source_file_id`
- `target_rule_id`
- `target_rule_snapshot`
- `created_by`
- `created_at`
- `reviewed_by`
- `reviewed_at`
- `review_comment`
- `merged_term_rule_set_id`
- `merged_draft_snapshot_hash`

## 8. 权限与鉴权处理

前端行为：

- 继续用 Bearer JWT。
- operator 可进入配置中心和术语建议页。
- admin-only 按钮通过 `RoleGate` 控制显示。
- 所有 admin-only API 仍以后端 403 作为最终保护。

禁止行为：

- 浏览器端不输入或保存 `X-Admin-Token`。
- operator 不允许指定 Template Version 创建任务。
- operator 不允许 publish、set-default、rollback、disable。

## 9. 加载态、空态、错误态处理

| 区域 | 加载态 | 空态 | 错误态 |
|---|---|---|---|
| 配置中心 | summary skeleton | 暂无待办 | 待办加载失败 |
| Template 列表 | 表格 loading | 暂无模板 | 403/503/网络失败 |
| Template 版本 | 表格 loading | 暂无版本 | 404/409/503 |
| Template 上传 | 按钮 loading | 未选择文件 | 非 docx、超大小、上传失败 |
| Proposal 列表 | 表格 loading | 暂无建议 | 403/网络失败 |
| Proposal 表单 | 提交中 | 不适用 | 表单校验、冲突、提交失败 |
| Term Rule Set | 面板 loading | 无 draft | 503、YAML 校验失败、publish 失败 |
| Translation Profile | 表单 loading | 暂无 profile | 503、保存失败 |

错误展示策略：

- 优先展示后端 `detail` 或 `error.message`。
- 保留 `error_code`、HTTP status 和 trace id。
- 409 冲突使用明确标题和处理建议。
- 503 resource service 未启用时提示当前部署模式不支持该功能。

## 10. 响应式与可访问性

- 桌面优先，兼容平板。
- 表格在窄屏可以横向滚动或切换为紧凑卡片。
- 操作按钮必须有文字，不只用图标。
- 状态不能只靠颜色表达。
- 分段编辑器支持键盘新增、删除和移动片段。
- 表单字段都有 label、错误提示和必填标记。
- 高风险操作弹窗必须说明影响范围。

## 11. 分阶段开发计划

### 阶段 1：后端最小合同补齐

目标：先补齐前端工作流必须依赖的可追溯后端合同。

任务：

- 为 Template Version 发布流程持久化验证证据：`verification_job_id`、`verification_note`、`verified_by`、`verified_at`。
- 为 Template Version `publish` 增加必填 `publish_reason`。
- 为 Template Version `set-default` 增加必填 `set_default_reason`。
- 新增 Term Rule Proposal 持久化模型和 API。
- Term Rule Proposal 支持 `pending_review`、`approved`、`rejected`。
- Term Rule Proposal 支持新增、编辑、禁用三类意图。
- 编辑和禁用 proposal 必须保存目标规则快照。
- Admin `approve` proposal 时原子合并到 Term Rule Set draft。
- 合并失败时 proposal 不得进入 `approved`。

验证：

- Template 验证证据刷新页面后仍可查看。
- 未填写验证任务 ID、验证说明或发布原因时，Template Version 不能发布。
- 术语 proposal 刷新页面后仍保留状态、提交人、目标规则快照和审核结果。

### 阶段 2：导航和配置中心

目标：V2 页面入口成型。

任务：

- 扩展 `AppLayout` 静态导航。
- 新增 `/settings`。
- 新增 `ConfigTodoSummary`。
- 新增 `RoleGate`。
- 配置中心顶部只展示配置发布相关待办。

验证：

- operator/admin 都能进入配置中心。
- operator 看不到 admin-only 操作。
- 403 不会触发 logout。

### 阶段 3：Template Profile

目标：admin 能完成模板验证、发布和设默认。

任务：

- 实现 templates API wrapper 和类型。
- 实现 Template 列表和详情页。
- 实现 Template Version 表格。
- 实现上传 Template draft version。
- 实现“创建验证任务”入口，仅 admin 可见。
- 复用 `documentJobsApi.create()` 创建指定 Template Version 验证任务。
- 实现验证证据弹窗。
- 实现 publish、set-default、disable。
- publish 和 set-default 拆成两个显式动作。

验证：

- admin 能完成一次 `Template draft -> 验证任务 -> 发布 -> 设默认`。
- operator 能查看模板和版本，但看不到上传、发布、设默认和禁用操作。
- 普通 `/jobs` 上传不暴露指定 Template Version 选择。
- Template 验证证据、发布原因和设默认原因都能在后端追溯。

### 阶段 4：Term Proposal

目标：operator 能提交术语建议，admin 能审核。

任务：

- 实现 term rule categories API wrapper。
- 实现 term rules 查询和目标规则选择。
- 实现 term proposals API wrapper。
- 实现 `/term-proposals`。
- 实现 operator proposal 轻量表单。
- 实现有序分段编辑器。
- 实现 plain/subscript/superscript 预览。
- 实现 admin 审核队列。
- 实现 approve/reject。
- 审核页展示当前规则、提交时快照和提议变更。
- 发现冲突时提示，不自动 rebase。

验证：

- operator 能提交一条 `VIN = V/plain + IN/subscript` proposal。
- admin 能 approve 该 proposal，并确认它合并到 Term Rule Set draft。
- rejected proposal 必须填写拒绝原因。
- 冲突 proposal 不允许无提示一键合并。

### 阶段 5：Term Rule Set 发布

目标：admin 能发布已合并 proposal 的规则集 draft。

任务：

- 实现 Term Rule Set 页面。
- 展示 default version、published versions 和 draft 摘要。
- 展示本次已 approve 但尚未发布的 proposals。
- 实现 publish，要求发布说明。
- 实现 set-default 和 rollback。
- 实现 admin YAML 高级编辑兜底。
- 暂不做完整 draft-vs-default diff。

验证：

- admin 能发布 Term Rule Set，新规则进入默认版本。
- draft 页面展示 `rule_count`、`enabled_rule_count`、`snapshot_hash`。
- 发布前能看到本次已 approve proposals。

### 阶段 6：Translation Profile

目标：admin 能管理翻译配置基础字段。

任务：

- 实现 translation profiles API wrapper 和类型。
- 实现 profile 列表和详情。
- 实现 draft 基础字段表单。
- 实现 publish、set-default、rollback。
- 处理 `503` 不可用态。

验证：

- admin 能编辑 draft 并发布 Translation Profile。
- operator 只读可见。
- 页面不提供 Prompt 正文编辑入口。

### 阶段 7：V2.1 端到端验收

目标：证明配置版本管理闭环可追溯、可审核、可回滚。

任务：

- 执行 Template 端到端验收：admin 完成一次 `Template draft -> 验证任务 -> 发布 -> 设默认`。
- 执行术语端到端验收：operator 提交 `VIN = V/plain + IN/subscript` proposal，admin approve 并发布 Term Rule Set。
- 覆盖 403、409、503、表单缺失、冲突提示和刷新恢复。

验证：

- Template 验证证据、发布原因和设默认原因都能在后端追溯。
- Term proposal 的提交、审核、合并、发布全链路状态可追溯。
- operator 无法执行 admin-only 操作。

## 12. 风险与验证方式

| 风险 | 影响 | 验证方式 | 处理建议 |
|---|---|---|---|
| Template 验证字段未落库 | 发布证据不可追溯 | 刷新后查看版本证据 | 阶段 1 先补后端合同 |
| Term Proposal 未持久化 | 审核流无法闭环 | operator 提交后刷新列表 | 阶段 1 新增 proposal API |
| approve 合并 draft 失败但状态已 approved | 规则未生效但状态误导 | 人为构造合并失败 | approve 必须原子处理 |
| operator 看到 admin-only 操作 | 权限风险 | 用 operator 登录巡检 | 前端 RoleGate + 后端 403 |
| 前端解析 YAML 产生不一致 | 规则发布风险 | 对比后端校验结果 | V2.1 不做复杂 diff，YAML 仅高级兜底 |
| Template publish+default 误操作 | 生产默认被误切换 | 操作回归 | UI 拆分两个动作并二次确认 |
| Translation prompt_version 填错 | 翻译配置失效 | publish 后测试 en2zh job | 后续让后端提供候选列表 |

## 13. 最小验收清单

- operator 能进入 `/settings` 和 `/term-proposals`。
- operator 只能只读查看配置。
- admin 能上传 Template draft version。
- admin 能创建指定 Template Version 验证任务。
- Template 发布前必须有验证证据和发布原因。
- Template 设默认必须有切换原因。
- 普通 `/jobs` 不暴露配置版本选择。
- operator 能提交 `VIN = V/plain + IN/subscript` proposal。
- admin 能 approve proposal 并合并到 draft。
- admin 能发布 Term Rule Set。
- rejected proposal 必须填写拒绝原因。
- 当前规则与快照冲突时显示冲突提示。
- admin 能编辑并发布 Translation Profile draft。
- operator 无法执行 admin-only API。

## 14. V2.2 方向

V2.1 保留以下演进方向，不在当前实现：

- 完整发布控制台。
- Template 自动质量检查。
- Term Rule Set draft-vs-default diff。
- Proposal 撤回和重新提交。
- 业务验证员角色。
- Prompt 正文管理。
- 运维监控 dashboard。

