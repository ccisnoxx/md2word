# Term Rule Governance Phase 2 Design

## Current State

Phase 1 已完成任务工作台闭环，任务详情可以带 `source_job_id/source_file_id/observed_term_rule_set_id/observed_term_rule_version` 跳转到术语 proposal 表单。归档的 `term-rule-workbench` 已新增 Admin-only `/settings/term-rules`，但它明确是只读规则检查和模拟页面。

后端现状：

- `GET /api/v1/term-rules`、`GET /api/v1/term-rules/{rule_id}`、`POST /api/v1/term-rules/simulate` 提供读取和模拟。
- Legacy `/api/v1/term-rules` 与 `/api/v1/term-rule-categories` 写接口在 MySQL versioned mode 下会拒绝写入。
- `/api/v1/term-rule-sets/{set_id}/draft` 和 `PUT /draft/rules` 已用完整 YAML 更新 draft。
- `/api/v1/term-rule-sets/{set_id}/publish`、`set-default`、`rollback` 已存在。
- `/api/v1/term-rule-sets/{set_id}/import` 和 `/export` 已在后端与 OpenAPI 中存在，但 `docs/api/term-rule-sets.md` 尚未完整同步。
- `/api/v1/term-rule-proposals` 已支持 create/update/disable proposal、approve、approve-and-publish、reject，并把 approved proposal 合入 Term Rule Set draft。

前端现状：

- `TermRuleSetPage.vue` 管理规则集版本、draft YAML 兜底、publish/default/rollback 和 approved proposals。
- `TermRuleWorkbenchPage.vue` 是只读检查/模拟台。
- `TermProposalsPage.vue` 提供 Operator proposal 表单和 Admin 审核队列。
- `termRuleSetsApi` 只有 YAML draft update、publish、set-default、rollback。
- 前端没有测试框架，当前最小验证是 `cd frontend && npm run build`。

## Architecture Boundary

生产术语规则治理的唯一写入面应是 Term Rule Set draft。

Legacy `/api/v1/term-rules` 写接口继续只作为 file/sqlite 兼容能力存在，不作为 Admin 工作台生产编辑路径。所有结构化 CRUD 都应在 `term-rule-sets` 下完成，并最终通过 publish/default/rollback 同步 live runtime store 和 runtime YAML。

`TermRuleWorkbenchPage` 保持只读和模拟，不加入编辑按钮。`TermRuleSetPage` 是治理入口：选择规则集、查看 draft、结构化编辑、diff、preflight、发布和回滚。

## Recommended Child Tasks

### 1. `term-rule-draft-crud-contract`

目标：为 draft 内规则和必要分类元数据提供结构化 API。

建议 API：

- `GET /api/v1/term-rule-sets/{set_id}/draft/rules`
- `POST /api/v1/term-rule-sets/{set_id}/draft/rules`
- `GET /api/v1/term-rule-sets/{set_id}/draft/rules/{rule_id}`
- `PATCH /api/v1/term-rule-sets/{set_id}/draft/rules/{rule_id}`
- `DELETE /api/v1/term-rule-sets/{set_id}/draft/rules/{rule_id}`
- `GET /api/v1/term-rule-sets/{set_id}/draft/categories`
- 可选：`POST/PATCH/DELETE /draft/categories`，仅在规则 CRUD 确认需要新增分类时实现。

语义：

- 所有写操作只更新 draft resource version。
- 每次写操作后返回新的 draft snapshot hash 和结构化规则对象。
- `DELETE` 表示从 draft 移除规则，不删除文件，不删除历史 published payload。
- `enabled=false` 是推荐的停用路径；物理移除规则需要明确确认。
- `source_term` 在 draft 内保持唯一，重复返回结构化 `409` 或 `400`。

### 2. `term-rule-set-diff-preflight`

目标：补齐版本 diff 和发布前校验。

建议 API：

- `GET /api/v1/term-rule-sets/{set_id}/diff?from=default&to=draft`
- `GET /api/v1/term-rule-sets/{set_id}/diff?from={version}&to=draft`
- `GET /api/v1/term-rule-sets/{set_id}/preflight`
- 可选：`POST /api/v1/term-rule-sets/{set_id}/preflight`，允许校验未保存的 YAML/草稿预览。

Diff 模型：

- `summary`: added / updated / disabled / removed / unchanged / total。
- `items[]`: `change_type`、`rule_id`、`source_term`、`category_id`、`before`、`after`、`changed_fields`。
- `base_version`、`target_version`、`base_snapshot_hash`、`target_snapshot_hash`。

Preflight 模型：

- `valid`
- `blocking`
- `summary`
- `errors[]`
- `warnings[]`
- `conflicts[]`
- `draft_snapshot_hash`
- `base_version`

校验项：

- YAML/store schema 是否有效。
- 分类是否存在、分类是否启用。
- `source_term` 是否重复。
- segments 是否非空且 render type 合法。
- disabled/removed 数量是否异常，作为 warning。
- draft 是否基于当前 default，若 default 已变化则 warning 或 blocking，需在设计中明确。
- approved unpublished proposals 是否会随 publish 被标记 published。

### 3. `term-rule-governance-ui`

目标：把结构化 CRUD、diff、preflight 接入 Admin 页面。

页面边界：

- `TermRuleSetPage.vue`
  - 增加 tabs 或分区：版本概览、Draft 规则、Diff、发布前校验、YAML 兜底。
  - Draft 规则列表支持分类、启用状态、关键词筛选。
  - 规则表单复用 `TermSegmentEditor` 和 `TermPreview`。
  - Publish dialog 在提交前展示 preflight 结果；blocking errors 禁用发布按钮。
  - YAML 高级编辑保留为折叠兜底，不作为主编辑路径。
- `TermRuleWorkbenchPage.vue`
  - 保持只读检查/模拟台，不新增编辑、删除、导入、导出或发布按钮。
- `TermProposalsPage.vue`
  - 只增强冲突展示和边界文案，不改 proposal 主语义。

### 4. `term-rule-proposal-boundary-conflicts`

目标：统一 proposal 与治理工作台边界，补结构化冲突响应。

后端冲突响应建议：

```json
{
  "code": "term_rule_proposal_conflict",
  "conflicts": [
    {
      "type": "stale_target_rule",
      "message": "目标规则已发生变化，请重新提交 proposal。",
      "target_rule_id": "..."
    }
  ]
}
```

前端行为：

- 审核时展示 `conflicts[]`。
- 不自动 rebase。
- 保留 pending 状态。
- 提供“查看当前规则”和“查看提交时快照”的人工判断入口。

## Data Model Additions

新增或补齐 Pydantic / TypeScript contracts：

- `TermRuleDraftRuleResponse`
- `TermRuleDraftRuleCreateRequest`
- `TermRuleDraftRuleUpdateRequest`
- `TermRuleDraftRuleDeleteResponse`
- `TermRuleSetDiffResponse`
- `TermRuleSetDiffItemResponse`
- `TermRuleSetPreflightResponse`
- `TermRuleGovernanceFindingResponse`
- `TermRuleConflictResponse`

这些模型应尽量复用现有 `TermRuleResponse`、`TermRuleSegmentWriteRequest`、`TermRuleImportValidationReportResponse` 的字段，避免并行定义两套术语规则形状。

## API Documentation

需要同步：

- `docs/api/term-rule-sets.md`
- `docs/api/term-rules.md`
- `docs/api/openapi.json`

特别注意：当前 `docs/api/term-rule-sets.md` 未列出已存在的 `import/export` 接口，Phase 2 文档更新应顺手补齐。

## Compatibility

- 现有 `GET /api/v1/term-rules` 读取能力保持兼容。
- 现有 proposal create/approve/reject API 保持路径兼容。
- 现有 `PUT /draft/rules` YAML 兜底保持兼容。
- Published versions 仍 immutable。
- Publish/default/rollback 仍是唯一同步 live runtime YAML 的动作。

## Risks

- 结构化 CRUD 与 YAML 兜底同时存在时，可能出现编辑入口认知混乱；UI 必须把 YAML 标为高级兜底。
- Draft 被 proposal approve 和 Admin CRUD 同时修改时，可能产生 stale snapshot 或重复术语冲突；需要结构化提示。
- Diff 如果只按 `rule_id` 比较，删除再新增同名规则可能难以表达；设计应同时展示 `source_term` 和 `rule_id`。
- Preflight 不能替代 publish 的最终后端校验；publish 仍需在服务端执行 blocking 校验。

## Rollback

- 子任务级别回滚优先：
  - 后端 contract 可通过移除新 endpoints 回退，保留旧 YAML update/publish 流程。
  - 前端 UI 可隐藏结构化编辑入口，保留当前 `TermRuleSetPage` YAML 兜底。
  - 结构化冲突响应应兼容旧自由文本展示，避免前后端分批发布时页面崩溃。
- 不需要数据迁移回滚，因为 draft/published payload 仍走现有 resource version store。
