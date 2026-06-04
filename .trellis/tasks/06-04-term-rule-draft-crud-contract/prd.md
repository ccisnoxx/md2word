# Term Rule Draft CRUD Contract

## Goal

为 Phase 2 术语规则治理建立后端结构化 CRUD 合同，让 Admin 能通过 Term Rule Set draft 新增、查看、编辑、启停和移除术语规则，而不是通过 legacy `/api/v1/term-rules` 直写 live runtime store。

本 task 只实现后端 contract、API 文档和后端测试；不接前端治理 UI，不做 diff / preflight，不改变 proposal 审核流，不运行 pdf-mineru / 翻译 / Word 生成主流程。

## Requirements

- Draft 规则读取
  - Admin 可以读取指定 Term Rule Set draft 内的规则列表。
  - 列表支持分页、分类、启用状态和关键词筛选，语义尽量对齐现有 `GET /api/v1/term-rules`。
  - Admin 可以读取 draft 内单条规则详情。
- Draft 规则创建
  - Admin 可以在 draft 中新增规则。
  - 新规则字段至少包含 `source_term`、`category_id`、`segments`、`apply_scope`、`case_sensitive`、`enabled`、`priority`、`custom_html`、`custom_markdown`、`notes`。
  - 不传 `id` 时后端生成稳定唯一 ID。
  - 创建只更新 draft，不改变当前 default version、live runtime store 或 runtime YAML。
- Draft 规则更新
  - Admin 可以更新 draft 中已有规则。
  - 支持启停规则，`enabled=false` 是主要停用路径。
  - 更新 segments 且未显式传 custom render 字段时，后端应沿用现有规则生成 markdown/html 的约定。
- Draft 规则移除
  - Admin 可以从 draft 中移除规则。
  - 移除只影响 draft 和后续发布版本，不删除历史 published payload，不做真实文件删除。
  - 该能力用于治理 draft，不等同于文件删除或物理清理。
- 写入保护和兼容
  - 所有写接口必须 admin-only。
  - MySQL resource service 未启用时返回 `503`，沿用 Term Rule Set versioning 约束。
  - Legacy `/api/v1/term-rules` 写保护保持不变。
  - 现有 `PUT /api/v1/term-rule-sets/{set_id}/draft/rules` YAML 兜底保持兼容。
- 错误和冲突
  - 重复 `source_term`、缺失分类、非法 segment、非法 apply scope 等返回明确错误。
  - 本 task 可以返回 `400` 处理 draft 内容错误；结构化 `409` 冲突可在后续 `term-rule-proposal-boundary-conflicts` task 统一增强。

## Non-goals

- 不实现前端编辑页面。
- 不实现 Term Rule Set diff。
- 不实现发布前 preflight。
- 不改 `TermRuleWorkbenchPage` 只读检查台。
- 不改 proposal approve / approve-and-publish / reject 语义。
- 不做真实文件删除。
- 不运行 pdf-mineru 解析、翻译或生成 Word 主流程。
- 不新增多租户规则集创建能力；继续只支持当前 `electronics-default` 规则集。

## Acceptance Criteria

- [ ] 新增 draft 规则列表和详情 API，并返回结构化规则数据。
- [ ] 新增 draft 规则 create API，成功后 draft rule count 增加，live runtime YAML 不变。
- [ ] 新增 draft 规则 patch API，可更新字段和启停规则，live runtime YAML 不变。
- [ ] 新增 draft 规则 delete API，可从 draft 移除规则，live runtime YAML 不变。
- [ ] Admin-only 写入鉴权通过；非 admin 写入被拒绝。
- [ ] 非 MySQL resource service 下 draft CRUD 返回 `503`。
- [ ] 重复 `source_term`、未知 `category_id`、空 segments、非法 render/apply scope 有测试覆盖。
- [ ] Legacy `/api/v1/term-rules` 写保护测试仍通过。
- [ ] `docs/api/term-rule-sets.md` 记录新增 draft CRUD API，并补齐当前已存在的 import/export API。
- [ ] `docs/api/openapi.json` 与 FastAPI schema 同步。
- [ ] 相关后端测试和 OpenAPI 测试通过。

## Notes

- Parent task: `.trellis/tasks/06-04-term-rule-governance-phase2`.
- Existing services to reuse:
  - `TermRuleSetVersionService`
  - `TermRuleYamlCodec`
  - `TermRuleImportValidationService`
  - existing `TermRuleResponse` / `TermRuleSegmentWriteRequest` shape.
- This task creates the backend contract consumed later by `term-rule-governance-ui`.
