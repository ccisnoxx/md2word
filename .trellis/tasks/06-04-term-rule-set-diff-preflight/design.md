# Term Rule Set Diff Preflight Design

## Scope

本任务新增后端 diff 和 preflight contract，并把 preflight blocking gate 接入现有 publish。它不增加前端治理 UI，不处理 proposal stale conflict 的完整结构化冲突展示。

## API Contract

### `GET /api/v1/term-rule-sets/{set_id}/diff`

查询参数：

- `from`: 默认 `default`。支持 `default` 或指定 published version。
- `to`: 默认 `draft`。本 child task 仅支持 `draft`。
- `include_unchanged`: 默认 `false`。为 `true` 时 `items[]` 包含 unchanged 规则。

响应：`TermRuleSetDiffResponse`

字段：

- `term_rule_set_id`
- `base_ref`
- `target_ref`
- `summary`
- `items`

`base_ref` / `target_ref` 使用 `TermRuleSetVersionRefResponse`：

- `ref`: 请求中的引用值，例如 `default`、`draft`、`2026.06.04-1`
- `version`: resolved version，例如 `draft` 或 published version
- `snapshot_hash`
- `rule_count`
- `enabled_rule_count`

`summary` 使用 `TermRuleSetDiffSummaryResponse`：

- `added`
- `updated`
- `disabled`
- `removed`
- `unchanged`
- `total`

`items[]` 使用 `TermRuleSetDiffItemResponse`：

- `change_type`: `added | updated | disabled | removed | unchanged`
- `rule_id`
- `source_term`
- `category_id`
- `changed_fields`
- `before`: `TermRuleResponse | null`
- `after`: `TermRuleResponse | null`

比较规则：

- 以 `rule.id` 作为主匹配键。
- `added`: base 不存在，target 存在。
- `removed`: base 存在，target 不存在。
- `disabled`: base `enabled=true`，target `enabled=false`；即使同时有其他字段变化，主 change_type 仍为 `disabled`，`changed_fields` 保留所有变化字段。
- `updated`: base 和 target 均存在，且除 disabled 主类型外存在字段变化。
- `unchanged`: base 和 target 均存在且字段等价。
- 字段等价比较覆盖 `category_id`、`source_term`、`rule_mode`、`apply_scope`、`case_sensitive`、`enabled`、`priority`、`segments`、`custom_html`、`custom_markdown`、`notes`。

### `GET /api/v1/term-rule-sets/{set_id}/preflight`

查询参数：

- `base`: 默认 `default`。支持 `default` 或指定 published version。

响应：`TermRuleSetPreflightResponse`

字段：

- `term_rule_set_id`
- `valid`
- `blocking`
- `base_ref`
- `draft_ref`
- `summary`
- `errors`
- `warnings`
- `conflicts`
- `diff_summary`

`summary` 使用 `TermRuleSetPreflightSummaryResponse`：

- `error_count`
- `warning_count`
- `conflict_count`
- `rule_count`
- `enabled_rule_count`

`errors[]` / `warnings[]` / `conflicts[]` 使用 `TermRuleGovernanceFindingResponse`：

- `severity`: `error | warning | conflict`
- `code`
- `message`
- `path`
- `rule_id`
- `source_term`
- `category_id`
- `metadata`

## Preflight Rules

Blocking errors:

- `invalid_term_rule_store`: draft store 无法通过现有 YAML/store validation。
- `missing_category`: draft rule 指向不存在分类。
- `disabled_category`: draft rule 指向已禁用分类但规则仍启用。
- `duplicate_source_term`: draft 内存在重复 `source_term`。
- `empty_segments`: draft rule segments 为空。

Warnings:

- `default_version_drift`: draft `base_version` 与当前 default version 不一致。
- `removed_rules`: diff 中存在 removed 规则。
- `disabled_rules`: diff 中存在 disabled 规则。
- `approved_unpublished_proposals`: publish 会把已 approved 且未发布的 proposal 标记为本次版本。

本 child task 不把 default drift 设为 blocking，因为现有 publish 兼容路径不支持 force publish 或 rebase。前端后续可以展示 warning 并要求人工确认。

Conflicts:

- 本 child task 预留 `conflicts[]` 字段，但不实现 proposal stale conflict。proposal 冲突收口留给后续 child。

## Publish Integration

`TermRuleSetVersionService.publish_draft` 在读取 draft 且创建 published record 前运行 preflight。

- 如果 `preflight.blocking=true`，抛出 `ValueError` 或专用异常，router 转换为 `400`：

```json
{
  "code": "term_rule_set_preflight_failed",
  "report": {}
}
```

- 如果只有 warnings，继续现有 publish 流程。
- `make_default=true` 的 live runtime store / runtime YAML 同步语义保持不变。
- `make_default=false` 仍只创建 published version，不改变默认指针和 runtime YAML。

## Service Shape

新增方法建议放在 `app/domains/term_rules/versioning_service.py`：

- `build_diff(term_rule_set_id, from_ref, to_ref, include_unchanged=False)`
- `build_preflight(term_rule_set_id, base_ref="default")`
- `_resolve_store_ref(term_rule_set_id, ref)`
- `_diff_stores(base_store, target_store, ...)`
- `_rule_comparison_payload(rule)`
- `_preflight_findings(...)`

Router 保持 thin：

- 参数校验交给 FastAPI Query。
- `FileNotFoundError` 转 `404`。
- `ValueError` 转 `400`。
- preflight blocking detail 由 publish endpoint 保持结构化。

## Data Model

新增 Pydantic models 放在 `app/domains/term_rules/schemas.py`：

- `TermRuleSetVersionRefResponse`
- `TermRuleSetDiffSummaryResponse`
- `TermRuleSetDiffItemResponse`
- `TermRuleSetDiffResponse`
- `TermRuleGovernanceFindingResponse`
- `TermRuleSetPreflightSummaryResponse`
- `TermRuleSetPreflightResponse`

尽量复用 `TermRuleResponse`，不新增第二套 rule shape。

## Tests

后端测试放在 `tests/test_fastapi_jobs_backend.py`：

- diff default vs draft: added / updated / disabled / removed / unchanged summary。
- diff 指定 published version vs draft。
- `include_unchanged=true` 返回 unchanged item。
- preflight valid + warning-only 报告。
- duplicate source term 或 missing category 产生 blocking error。
- publish 遇 blocking preflight 返回结构化 `400`，且不创建 published version，不刷新 runtime YAML。
- warning-only publish 仍成功。
- file backend 返回 `503`。
- OpenAPI snapshot 更新。

## Documentation

同步：

- `docs/api/term-rule-sets.md`
- `docs/api/openapi.json`

## Rollback

移除新增 diff/preflight endpoints、schemas、service methods 和 publish preflight gate 即可回退。旧 YAML draft update、Child 1 draft CRUD、publish/default/rollback 流程仍保留。
