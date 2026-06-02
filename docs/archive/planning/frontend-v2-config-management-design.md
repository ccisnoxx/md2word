---
doc_type: frontend-design
slug: frontend-v2-config-management-design
component: frontend-config-management
status: current
summary: 前端 V2 配置版本管理设计文档，覆盖 Template Profile、Term Rule Set、Translation Profile 和术语 proposal 工作流。
tags: [frontend, design, v2, config-management, templates, term-rules, translation-profiles]
last_reviewed: 2026-06-01
---

# 前端 V2 配置版本管理设计文档

> 本文归档前端 V2 需求和交互设计基线。V2.1 的目标是把 V1 已完成的内部任务工作台扩展为“配置版本管理闭环”，不做外部客户门户，也不做完整后台管理系统。

## 1. 项目背景

### 1.1 已知事实

- V1 前端已完成内部文档转换工作台，覆盖登录、PDF 上传、任务列表、任务详情、事件、下载、重试、取消和归档。
- 当前前端技术栈已经是 Vue 3、Vite、TypeScript、Element Plus、Pinia、Vue Router 和 Axios。
- 后端已有 Template Profile、Term Rule Set、Translation Profile 的版本能力。
- 后端 admin 依赖已经支持 Bearer admin JWT，浏览器前端不需要也不应该保存 `X-Admin-Token`。
- 当前后端已有 term rule `segments[]` 模型，片段支持 `plain`、`subscript`、`superscript`。
- 当前后端还没有独立 Term Rule Proposal 模型，也没有 Template Version 验证证据持久化字段。

### 1.2 推断

- V2 的主要用户价值不是“继续上传转换”，而是让内部人员安全地调整影响转换结果的配置。
- 模板变更、术语变更和翻译配置变更都可能影响后续任务结果，必须可审核、可追溯、可回滚。
- operator 经常能发现术语问题，但不应直接修改生产规则。
- admin 需要一个清晰入口判断哪些配置还未验证、哪些建议还未审核、哪些 draft 尚未发布。

### 1.3 建议

- V2.1 按资源类型落地页面：Template Profile -> Term Rule Set -> Translation Profile。
- 配置中心顶部保留轻量待办汇总，但不直接做完整发布控制台。
- Template Profile 优先落地版本验证、发布和设默认闭环。
- Term Rule Set 优先落地 operator proposal、admin 审核和规则集发布闭环。
- Translation Profile 只做基础字段版本管理，不做 Prompt 正文编辑。

## 2. 产品定位

V2.1 是内部配置版本管理工作台，服务于内部文档交付和运营团队。

它要解决的问题：

- 新模板版本发布前如何验证。
- 术语规则如何由一线人员提交、管理员审核、版本化发布。
- 翻译配置如何以低风险方式编辑 draft、发布和回滚。
- 配置变更如何保留最小追溯证据。

它不解决的问题：

- 外部客户自助转换门户。
- 复杂多级权限系统。
- 在线 Word 校对和质量评分。
- 运维监控 dashboard。
- AI Prompt 正文编辑器。

## 3. 目标用户

| 用户类型 | 角色 | V2.1 权限 | 核心诉求 |
|---|---|---|---|
| 内部文档交付人员 | `operator` | 任务工作台、配置只读、提交术语 proposal | 看清当前配置，反馈术语问题，完成日常转换交付 |
| 内部配置管理员 | `admin` | 配置读写、模板发布、术语审核、规则集发布、翻译配置发布 | 安全管理影响转换结果的配置版本 |
| 技术运营人员 | `admin` | 配置管理和追溯 | 排查配置变更导致的转换结果变化 |

## 4. 核心使用场景

### 4.1 Template Profile 验证和发布

1. admin 进入 Template Profile 页面。
2. admin 查看当前默认模板和已有版本。
3. admin 上传新的 Template draft version。
4. admin 从该 Template Version 页面创建验证任务。
5. 验证任务完成后，admin 填写验证任务 ID 和验证说明。
6. admin 发布该 Template Version，并填写发布原因。
7. admin 如需切换生产默认版本，再单独点击设为默认，并填写切换原因。

### 4.2 Operator 提交术语建议

1. operator 进入 `/term-proposals`。
2. operator 选择新增、编辑或禁用。
3. 新增时填写 `source_term`、分类、分段展示建议、说明和可选来源。
4. 编辑或禁用时必须选择一个现有规则作为目标。
5. operator 提交后 proposal 状态为 `pending_review`。
6. operator 可以查看自己的 proposal 状态和审核结果。

### 4.3 Admin 审核术语建议

1. admin 进入 `/term-proposals`，默认看到待审核队列。
2. admin 查看 operator 提交内容、当前规则和提交时规则快照。
3. 若发现当前规则和快照不一致，页面显示冲突提示，不自动 rebase。
4. admin 可以 reject 并填写拒绝原因。
5. admin approve 时将 proposal 原子合并到 Term Rule Set draft。
6. approved 只代表已合并 draft，不代表生产生效。

### 4.4 Term Rule Set 发布

1. admin 进入 Term Rule Set 页面。
2. 页面展示 default version、published versions 和当前 draft 摘要。
3. 页面展示本次已 approve 但尚未发布的 proposals。
4. admin 填写发布说明并 publish。
5. 发布成功后新规则进入默认版本，后续任务使用新规则。

### 4.5 Translation Profile 基础管理

1. admin 进入 Translation Profile 页面。
2. admin 查看默认版本、published versions 和 draft。
3. admin 编辑基础字段。
4. admin publish、set-default 或 rollback。
5. 页面不提供 Prompt 正文编辑。

## 5. 信息架构

V2.1 使用静态一级导航：

| 一级导航 | 路由 | 说明 |
|---|---|---|
| 任务工作台 | `/jobs` | 保留 V1 主链路 |
| 配置中心 | `/settings` | 配置版本管理入口 |
| 术语建议 | `/term-proposals` | operator 提交和 admin 审核 proposal |

配置中心二级页面：

| 页面 | 路由 | 说明 |
|---|---|---|
| 配置中心首页 | `/settings` | 待办汇总和资源入口 |
| 模板配置 | `/settings/templates` | Template Profile 列表 |
| 模板详情 | `/settings/templates/:templateId` | 版本列表、上传、验证、发布 |
| 术语规则集 | `/settings/term-rule-sets` | draft 摘要、发布、回滚 |
| 翻译配置 | `/settings/translation-profiles` | draft 基础字段、发布、回滚 |

## 6. 页面清单

| 页面 | 用户 | 主要内容 | V2.1 动作 |
|---|---|---|---|
| `/settings` | operator/admin | 配置待办、资源入口 | 查看待办 |
| `/settings/templates` | operator/admin | 模板列表、默认模板 | 查看 |
| `/settings/templates/:templateId` | operator/admin | 模板详情和版本列表 | admin 上传 draft、创建验证任务、发布、设默认、禁用 |
| `/settings/term-rule-sets` | operator/admin | 规则集版本、draft 摘要、已 approve proposals | admin 发布、set-default、rollback、YAML 高级编辑 |
| `/settings/translation-profiles` | operator/admin | 翻译配置版本和 draft | admin 编辑基础字段、发布、set-default、rollback |
| `/term-proposals` | operator/admin | 我的建议、待审核队列、proposal 表单 | operator 提交，admin 审核 |

## 7. 用户流程

### 7.1 Template Version 流程

```text
上传 draft version
-> 创建验证任务
-> 验证任务 succeeded
-> 填写 verification_job_id / verification_note
-> publish with publish_reason
-> set-default with set_default_reason
```

约束：

- 只有 admin 可以创建指定 Template Version 的验证任务。
- 普通 `/jobs` 上传不暴露 Template Version 选择。
- Template 发布和设默认是两个显式动作，不提供默认勾选的 publish+default 快捷操作。
- 验证证据绑定到 Template Version，不要求每次 set-default 都重新验证。

### 7.2 Term Proposal 流程

```text
operator 提交 proposal
-> pending_review
-> admin 审核
-> approve 合并到 draft 或 reject
-> admin 发布 Term Rule Set
```

proposal 状态：

| 状态 | 含义 |
|---|---|
| `pending_review` | 已提交，等待 admin 审核 |
| `approved` | 已审核通过，并已成功合并到 Term Rule Set draft |
| `rejected` | 已拒绝，必须有拒绝原因 |

约束：

- 不做撤回、重开、多级审核。
- 用户需要修改 rejected 内容时，提交新 proposal。
- approve 是原子动作；合并失败时不得进入 `approved`。

### 7.3 Translation Profile 流程

```text
查看 profile
-> 编辑 draft 基础字段
-> publish
-> set-default 或 rollback
```

约束：

- 不编辑 Prompt 正文。
- `prompt_version` 只作为配置字段处理。
- MySQL resource service 未启用时展示 `503` 不可用态。

## 8. MVP 范围

### 8.1 V2.1 进入范围

- 静态导航扩展。
- 配置中心首页和轻量待办汇总。
- Template Profile 既有模板版本管理。
- Template 发布前轻量验证。
- Operator 术语 proposal 提交。
- Admin 术语 proposal 审核。
- Term Rule Set draft 摘要和发布。
- Translation Profile 基础字段版本管理。
- 后端最小合同补齐：Template 验证字段、Term Rule Proposal。

### 8.2 V2.1 不进入范围

- 新建或删除 Template Profile。
- 完整 draft-vs-default diff。
- 在线 Word 自动评分或自动对比。
- Prompt 正文编辑。
- 完整发布控制台。
- 运维监控 dashboard。
- 复杂 RBAC、权限组、菜单管理。
- operator 选择 draft/template version 创建任务。

## 9. 功能需求

### 9.1 Template Profile

| ID | 功能 | 权限 | 验收 |
|---|---|---|---|
| TP-001 | 查看模板列表和默认模板 | operator/admin | 可看到模板 ID、名称、版本、默认状态 |
| TP-002 | 查看模板版本列表 | operator/admin | 可看到 draft/published/default/disabled 状态 |
| TP-003 | 上传 Template draft version | admin | 成功生成 draft version |
| TP-004 | 创建验证任务 | admin | 使用指定 Template Version 创建任务 |
| TP-005 | 填写验证证据 | admin | 保存 `verification_job_id`、`verification_note`、`verified_by`、`verified_at` |
| TP-006 | 发布 Template Version | admin | 必须有验证证据和 `publish_reason` |
| TP-007 | 设为默认 | admin | 必须填写 `set_default_reason` |
| TP-008 | 禁用非默认版本 | admin | 默认版本不可禁用 |

### 9.2 Term Proposal

| ID | 功能 | 权限 | 验收 |
|---|---|---|---|
| TRP-001 | 查看我的 proposal | operator/admin | 默认按用户展示自己提交内容 |
| TRP-002 | 新增规则 proposal | operator/admin | 可提交 source term、分类、segments、说明 |
| TRP-003 | 编辑规则 proposal | operator/admin | 必须绑定现有规则并保存规则快照 |
| TRP-004 | 禁用规则 proposal | operator/admin | 必须绑定现有规则，只填写禁用原因 |
| TRP-005 | 审核队列 | admin | 默认展示 `pending_review` |
| TRP-006 | approve proposal | admin | 成功合并到 Term Rule Set draft 后状态变为 `approved` |
| TRP-007 | reject proposal | admin | 必须填写拒绝原因 |
| TRP-008 | 冲突提示 | admin | 当前规则与快照不一致时提示，不自动 rebase |

### 9.3 术语分段编辑器

| 字段 | 说明 |
|---|---|
| `segment_text` | 片段文本 |
| `render_type` | `plain`、`subscript`、`superscript` |
| 顺序 | 用户可调整或删除片段 |
| 预览 | 实时展示普通、下标、上标效果 |

示例：

| 顺序 | 文本 | 样式 |
|---|---|---|
| 1 | V | `plain` |
| 2 | IN | `subscript` |

提交含义：`source_term=VIN`，展示建议为 `V/plain + IN/subscript`。

### 9.4 Term Rule Set

| ID | 功能 | 权限 | 验收 |
|---|---|---|---|
| TRS-001 | 查看规则集详情 | operator/admin | 可看到 default version 和 published versions |
| TRS-002 | 查看 draft 摘要 | operator/admin | 可看到 `rule_count`、`enabled_rule_count`、`snapshot_hash` |
| TRS-003 | 查看本次已 approve proposals | admin | 发布前可核对来源 |
| TRS-004 | 发布规则集 | admin | 必须填写 `publish_reason` |
| TRS-005 | set-default / rollback | admin | 只允许指向 published version |
| TRS-006 | YAML 高级编辑 | admin | 有校验和强提示，不作为主路径 |

### 9.5 Translation Profile

| ID | 功能 | 权限 | 验收 |
|---|---|---|---|
| TLP-001 | 查看 profile 列表和详情 | operator/admin | 可看到默认版本和 published versions |
| TLP-002 | 编辑 draft 基础字段 | admin | 可保存 draft |
| TLP-003 | publish | admin | 生成 published version |
| TLP-004 | set-default / rollback | admin | 默认指针切换成功 |

允许编辑字段：

- `target_language`
- `domain`
- `prompt_version`
- `model`
- `max_pages_per_batch`
- `max_chars_per_batch`

## 10. 权限设计

| 场景 | operator | admin |
|---|---|---|
| 查看配置中心 | 是 | 是 |
| 查看模板和版本 | 是 | 是 |
| 上传 Template draft | 否 | 是 |
| 创建指定版本验证任务 | 否 | 是 |
| 发布或设默认 Template | 否 | 是 |
| 提交 term proposal | 是 | 是 |
| 审核 term proposal | 否 | 是 |
| 发布 Term Rule Set | 否 | 是 |
| 编辑 Translation Profile draft | 否 | 是 |

鉴权约束：

- 浏览器端统一使用 Bearer JWT。
- 前端不保存 `X-Admin-Token`、`ADMIN_TOKEN` 或 `X-Jobs-Token`。
- 403 只展示无权限，不自动退出。

## 11. 状态覆盖要求

### 11.1 页面状态

- 加载中。
- 空态。
- 筛选后为空。
- 403 无权限。
- 404 资源不存在。
- 409 状态冲突。
- 503 resource service 未启用。
- 网络失败。

### 11.2 Template 状态

- 无版本。
- draft version。
- published version。
- default version。
- disabled version。
- 待验证。
- 已验证。
- 发布中。
- 设默认中。
- 操作失败。

### 11.3 Proposal 状态

- 新建表单。
- 提交中。
- `pending_review`。
- `approved`。
- `rejected`。
- 审核冲突。
- 合并失败。

### 11.4 Term Rule Set 状态

- 无 draft。
- 有 draft。
- draft 摘要加载失败。
- 有已 approve 但未发布 proposal。
- publish 中。
- rollback 中。

### 11.5 Translation Profile 状态

- resource service 不可用。
- 无默认版本。
- 有 draft。
- published/default。
- 保存失败。
- 发布失败。

## 12. 配置中心待办汇总

V2.1 只展示配置发布相关待办，不做运维监控。

待办项：

- 待审核 term proposals 数量。
- 已 approve 但尚未发布的 term proposals 数量。
- 待验证或待发布的 Template draft versions 数量。
- Translation Profile 存在未发布 draft 时提示。

不展示：

- job 失败数。
- health metrics。
- 磁盘、worker、Redis、MySQL 状态。

## 13. 非目标

- 不做外部客户门户。
- 不做完整后台管理系统。
- 不做新建/删除 Template Profile。
- 不做完整规则 diff。
- 不做在线 Word 自动质量检查。
- 不做 Prompt 正文编辑器。
- 不做完整发布控制台。
- 不做运维监控 dashboard。
- 不在普通任务上传中开放配置版本选择。

## 14. 验收标准

1. operator 能进入配置中心，只读查看 Template、Term Rule Set、Translation Profile。
2. operator 看不到 admin-only 操作按钮。
3. admin 能上传 Template draft version。
4. admin 能从 Template Version 页面创建指定版本验证任务。
5. Template 发布前必须填写成功验证任务 ID、验证说明和发布原因。
6. Template 设默认必须填写切换原因。
7. Template 发布和设默认是两个显式动作。
8. operator 能提交 `VIN = V/plain + IN/subscript` proposal。
9. 编辑和禁用 proposal 必须绑定现有规则。
10. admin 能 approve proposal，并确认它合并到 Term Rule Set draft。
11. rejected proposal 必须填写拒绝原因。
12. 当前规则与 proposal 快照冲突时，页面提示冲突，不自动 rebase。
13. admin 能发布 Term Rule Set，使已 approve proposal 生效。
14. admin 能编辑 Translation Profile draft 基础字段并发布。
15. 页面不提供 Prompt 正文编辑。

## 15. Open Questions

| 问题 | 影响 | 建议 |
|---|---|---|
| Template 验证任务是否必须校验 `template_version_id` 匹配 | 影响发布安全性 | V2.1 至少校验 `status=succeeded`，后端优先补匹配校验 |
| Term Proposal API payload 具体格式 | 影响前端表单和审核页 | 后端最小合同阶段先定 schema |
| Translation Profile `prompt_version` 是否有候选列表 | 影响表单校验 | 没有候选列表时先用文本输入，后续改下拉 |
| V2.2 是否做完整发布控制台 | 影响信息架构演进 | V2.1 保留待办汇总，暂不做聚合发布台 |

