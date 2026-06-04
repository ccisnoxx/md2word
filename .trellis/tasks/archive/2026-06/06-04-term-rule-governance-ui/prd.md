# Term Rule Governance UI

## Goal

把 Child 1 的结构化 draft rule CRUD 和 Child 2 的 diff/preflight contract 接入 Admin 规则集治理页面，让 Admin 可以在 `TermRuleSetPage` 内完成 draft 规则维护、查看发布影响、处理发布前 blocking/warning，并保留 YAML 高级兜底。

本 child task 只做前端 UI 和前端 API/type contract。后端 diff/preflight/CRUD contract 已由前两个 child task 提供。

## Requirements

- Draft 规则治理
  - Admin 可在 `TermRuleSetPage` 查看 draft rules。
  - Admin 可新增、编辑、启停和删除 draft rule。
  - 编辑表单覆盖 `source_term`、`category_id`、segments、`apply_scope`、`case_sensitive`、`enabled`、`priority`、`custom_html`、`custom_markdown`、`notes`。
  - 表单复用 `TermSegmentEditor` 和 `TermPreview`，不再新增一套 segment 编辑模型。
  - 删除操作必须二次确认，且说明只删除 draft rule，不做真实文件删除。
- Diff
  - Admin 可查看 draft 相对 default 的 diff summary。
  - Diff 明细至少展示 added / updated / disabled / removed。
  - 支持查看 before / after 关键字段，能定位到具体 rule。
- Preflight
  - 页面加载和发布前展示 preflight 报告。
  - Blocking errors 禁用发布按钮。
  - Warnings 展示但不阻止发布。
  - Publish API 返回 `term_rule_set_preflight_failed` 时，页面展示后端 report，不依赖自由文本。
- Existing flow compatibility
  - 保留 Published versions、set-default、rollback。
  - 保留 approved proposals 核对区。
  - 保留 YAML 高级编辑兜底，但不作为默认编辑入口。
  - 保留 `TermRuleWorkbenchPage` 只读检查/模拟定位，不加入新增、编辑、删除、导入、导出或发布按钮。

## Non-goals

- 不修改后端 API contract。
- 不运行 pdf-mineru 解析、翻译或 Word 生成主流程。
- 不做真实文件删除。
- 不实现 proposal stale conflict 结构化 `409` 收口；该能力留给后续 child。
- 不实现批量规则编辑、批量导入向导或自动 rebase。
- 不新增复杂权限模型；沿用现有 `RoleGate` 和 admin API 鉴权。
- 不新增前端测试框架；本轮最小验证为 `cd frontend && npm run build`。

## Acceptance Criteria

- [ ] `TermRuleSetPage` 可加载 draft rules，并提供分类、启用状态、关键词筛选。
- [ ] Admin 可通过结构化表单新增 draft rule。
- [ ] Admin 可编辑 existing draft rule 并看到 draft summary 更新。
- [ ] Admin 可启停 draft rule。
- [ ] Admin 可删除 draft rule，删除前有确认提示。
- [ ] 页面展示 diff summary 和 changed items。
- [ ] 页面展示 preflight errors/warnings/conflicts。
- [ ] Blocking preflight 禁用发布按钮。
- [ ] Publish 失败时可展示结构化 preflight report。
- [ ] YAML 高级兜底仍可用。
- [ ] `TermRuleWorkbenchPage` 保持只读，不新增编辑能力。
- [ ] `cd frontend && npm run build` 通过。

## Notes

- Parent task: `.trellis/tasks/06-04-term-rule-governance-phase2`。
- Backend dependencies:
  - `.trellis/tasks/06-04-term-rule-draft-crud-contract`
  - `.trellis/tasks/06-04-term-rule-set-diff-preflight`
- Current `TermRuleSetPage` already has version list、draft summary、YAML fallback、publish/default/rollback 和 approved proposal review section.
