# Term Rule Governance UI Design

## Scope

本任务只改前端治理页面和前端 API/type。主入口为 `frontend/src/pages/TermRuleSetPage.vue`，页面消费既有后端 contract，不新增后端行为。

## UX Structure

`TermRuleSetPage` 保持当前单页 Admin 治理入口，建议按以下信息层组织：

1. Header
   - 刷新按钮。
   - MySQL resource service unavailable warning 保持现状。
2. Top summary grid
   - 规则集选择。
   - Draft 摘要。
   - Preflight 状态摘要。
3. Draft rules section
   - 筛选工具栏：分类、启用状态、关键词。
   - 表格列：source term、preview、category、scope、priority、enabled、actions。
   - Admin actions：新增、编辑、启停、删除。
4. Diff section
   - Summary counters：added、updated、disabled、removed、unchanged。
   - Changed items table：change_type、source_term、changed_fields、before/after preview。
5. Published versions
   - 保持现有 set-default / rollback。
6. Approved proposals
   - 保持现有核对区。
7. YAML advanced fallback
   - 保持折叠兜底；文案明确“高级兜底”。

不在 `TermRuleWorkbenchPage` 加编辑入口。可选仅添加跳转到治理页的只读说明，但本 child task 默认不触碰它。

## Frontend API Contract

更新 `frontend/src/api/types.ts`：

- `TermRuleCreateRequest`
- `TermRuleUpdateRequest`
- `TermRuleDraftRuleMutationResponse`
- `TermRuleDraftRuleDeleteResponse`
- `TermRuleSetVersionRefResponse`
- `TermRuleSetDiffSummaryResponse`
- `TermRuleSetDiffItemResponse`
- `TermRuleSetDiffResponse`
- `TermRuleGovernanceFindingResponse`
- `TermRuleSetPreflightSummaryResponse`
- `TermRuleSetPreflightResponse`

更新 `frontend/src/api/termRuleSets.ts`：

- `listDraftRules(setId, params)`
- `getDraftRule(setId, ruleId)`
- `createDraftRule(setId, payload)`
- `updateDraftRule(setId, ruleId, payload)`
- `deleteDraftRule(setId, ruleId)`
- `diff(setId, params)`
- `preflight(setId, params)`

保留现有：

- `list`
- `get`
- `getDraft`
- `updateDraft`
- `publish`
- `setDefault`
- `rollback`

## Page State

新增状态建议：

- `draftRules`
- `draftRuleTotal`
- `draftRuleFilters`
- `draftRulesLoading`
- `ruleDialog`
- `savingRule`
- `deletingRuleId`
- `diffReport`
- `diffLoading`
- `preflightReport`
- `preflightLoading`

`loadSelectedSet` 应并行加载：

- detail
- draft
- draft rules
- diff
- preflight

写操作后刷新：

- draft summary
- draft rules
- diff
- preflight
- YAML text

## Rule Form

表单字段：

- `source_term`
- `category_id`
- `segments`
- `apply_scope`
- `case_sensitive`
- `enabled`
- `priority`
- `custom_html`
- `custom_markdown`
- `notes`

新增时：

- `segments` 默认一条 `{ segment_text: "", render_type: "plain" }`。
- `enabled=true`。
- `case_sensitive=true`。
- `apply_scope="both"`。
- `priority=100`。

编辑时：

- `TermRuleResponse.segments` 转为 `TermRuleSegmentWriteRequest[]`。
- 只发送当前表单字段即可，不需要计算 field diff。

## Preflight Publish Flow

`openPublishDialog` 前应刷新 preflight。

- `preflight.blocking=true` 时允许打开 dialog 查看报告，但 publish button 禁用。
- publish dialog 中展示 errors/warnings/conflicts。
- `term_rule_set_preflight_failed` 失败时，从 error detail 提取 report 并展示。

## Styling

沿用现有 Element Plus + scoped SCSS：

- 页面保持 utilitarian dashboard 风格。
- 避免嵌套 card。
- 筛选工具栏使用 `.toolbar.filters` 风格。
- 表格和 drawer/dialog 承载主要工作流。
- 移动端规则表单和筛选器使用单列布局。

## Verification

- `cd frontend && npm run build`
- 可选手动 smoke：
  - 打开 `/settings/term-rule-sets`
  - 刷新列表
  - 新增 rule
  - 编辑 rule
  - 停用 rule
  - 查看 diff/preflight
  - blocking 时发布按钮禁用

## Risks

- `TermRuleSetPage.vue` 已较大，直接继续堆叠会变长；本 child task 可以抽出小型局部组件，但不要引入大型抽象。
- 前端无测试框架，build 只能覆盖类型和编译，不能替代浏览器 smoke。
- 后端 blocking report 结构已稳定，但 proposal conflict 仍是后续 child 范围。

## Rollback

隐藏或移除 Draft rules / Diff / Preflight 新分区，保留原页面的 draft summary、published versions、approved proposals 和 YAML fallback 即可回退。
