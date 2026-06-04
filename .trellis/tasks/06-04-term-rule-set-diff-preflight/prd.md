# Term Rule Set Diff Preflight

## Goal

补齐 Term Rule Set draft 的后端 diff 与发布前校验 contract，让 Admin 在进入前端治理 UI 之前，已经有稳定 API 能判断 draft 相对默认版本的发布影响，并让 publish 在服务端执行 blocking preflight gate。

本 child task 只处理后端 contract、API 文档、OpenAPI 和后端测试。不实现前端页面，不改变 `TermRuleWorkbenchPage` 只读定位，不处理 proposal stale conflict 的完整边界收口。

## Requirements

- Draft diff
  - 支持比较 `draft` 与当前 `default` published version。
  - 支持比较 `draft` 与指定 published version。
  - 响应包含 `base_version`、`target_version`、snapshot hash、summary 和 changed items。
  - Summary 至少包含 `added`、`updated`、`disabled`、`removed`、`unchanged`、`total`。
  - Item 需要能定位 `rule_id`、`source_term`、`category_id`、`change_type`、`changed_fields`、`before`、`after`。
  - 默认只返回 changed items；可选返回 unchanged items。
- Preflight
  - 支持查询当前 draft 的发布前校验报告。
  - 报告区分 blocking errors 和 warnings。
  - Blocking errors 阻止 publish。
  - Warnings 不阻止 publish，但必须稳定返回给前端展示。
  - 校验应复用现有 term rules YAML / store validation 能力，并补充治理层检查。
- Publish gate
  - `POST /api/v1/term-rule-sets/{set_id}/publish` 在创建 published version 前必须运行 preflight。
  - preflight 有 blocking finding 时返回 `400`，detail 使用结构化 `{code, report}`。
  - warnings 不改变现有 publish 成功路径。
- Compatibility
  - 保留现有 `PUT /draft/rules` YAML 兜底。
  - 保留 Child 1 结构化 draft rule CRUD contract。
  - 保留 existing import/export、set-default、rollback 语义。
  - 不刷新 runtime YAML，除非 existing publish/default/rollback 语义本来会刷新。

## Non-goals

- 不实现前端 diff/preflight UI。
- 不改 `TermRuleWorkbenchPage` 的只读检查台定位。
- 不做 proposal stale conflict 的结构化 `409` 收口；该能力留给 `term-rule-proposal-boundary-conflicts`。
- 不做自动 rebase、自动冲突解决或 force publish。
- 不做真实文件删除。
- 不运行 pdf-mineru 解析、翻译或 Word 生成主流程。
- 不引入数据库迁移或改变 resource version payload 基本结构。

## Acceptance Criteria

- [ ] 新增 diff API，可返回 draft 相对 default 或指定 published version 的结构化差异。
- [ ] Diff summary 正确统计 added / updated / disabled / removed / unchanged / total。
- [ ] Diff item 能返回 before / after 规则快照和 changed_fields。
- [ ] 新增 preflight API，可返回 blocking errors、warnings、summary、draft/base metadata。
- [ ] Invalid draft store 或治理层 blocking finding 会阻止 publish，并返回结构化 `400`。
- [ ] Warning-only preflight 不阻止 publish。
- [ ] Publish 成功路径仍只在 `make_default=true` 时同步 live runtime store 和 runtime YAML。
- [ ] 后端测试覆盖 diff、preflight、publish blocking、warning-only publish、OpenAPI snapshot。
- [ ] `docs/api/term-rule-sets.md` 与 `docs/api/openapi.json` 同步更新。

## Notes

- Parent task: `.trellis/tasks/06-04-term-rule-governance-phase2`。
- Previous child: `.trellis/tasks/06-04-term-rule-draft-crud-contract`。
- This task assumes Child 1 draft rule CRUD contract exists and remains stable.
