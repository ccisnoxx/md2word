---
doc_type: lib-api-ref
entry: term-rule-sets
category: endpoint
status: current
source_files:
  - app/api/v1/router.py
  - app/domains/term_rules/sets_router.py
  - app/domains/term_rules/write_guard.py
  - app/api/dependencies.py
  - app/domains/audit/models.py
  - app/domains/audit/service.py
  - app/domains/term_rules/versioning_service.py
  - app/domains/resources/service.py
  - app/domains/term_rules/schemas.py
summary: Term-rule-sets API 在 MySQL resource service 下提供术语规则集 draft、结构化 draft rule CRUD、diff/preflight、import/export、publish、set-default、rollback 和成功动作审计。
tags: [term-rules, resource-versioning, api, audit]
last_reviewed: 2026-06-21
---

## 概述

当前 `term-rule-sets` 统一挂在 `/api/v1/term-rule-sets` 下，用于管理术语规则集的草稿、结构化 draft 规则、diff、发布前校验、导入导出、发布版本、默认指针和回滚。

当前约束：

- 需要 `JOBS_REPOSITORY_BACKEND=mysql`，否则接口返回 `503`
- MVP 只支持默认规则集 `electronics-default`
- draft 更新不写 `term_rules_store.json`，也不刷新 `runtime_subscripts_dictionary.yaml`
- 结构化 draft rule CRUD 只修改 resource version draft，不改变 legacy live store、runtime YAML 或 published version
- diff / preflight 只读取 draft 和 published version，不改变 runtime YAML
- publish 在创建 published version 前执行 blocking preflight gate
- publish / set-default / rollback 只有目标版本成为默认 published 版本时，才同步 legacy live runtime store 和 runtime YAML
- MySQL versioned mode 下，legacy `/term-rules` 和 `/term-rule-categories` 写接口会拒绝直写
- import / export / publish / set-default / rollback 成功后会写 audit event
- publish 成功后会把已 approve 且尚未发布的 term rule proposals 关联到本次 published version
- 读取 draft、diff、preflight 和结构化 draft rules 需要 Bearer JWT，兼容 legacy `X-Admin-Token`；写入、导入导出、发布、设默认和回滚需要 Bearer admin JWT 或 legacy `X-Admin-Token`
- draft 写入接口兼容可选 `expected_snapshot_hash`；客户端传入后，服务会在写入前校验当前 draft `snapshot_hash`，不匹配时返回 `409 draft_snapshot_conflict`

## API 参考

### `GET /api/v1/term-rule-sets`

- 用途：列出当前支持的术语规则集。
- 认证：Bearer JWT；兼容 legacy `X-Admin-Token`。
- 前置：需要 MySQL resource service。
- 响应：
  - `items[].id`
  - `items[].default_version`
  - `items[].version_count`
  - `items[].rule_count`
  - `items[].enabled_rule_count`

### `GET /api/v1/term-rule-sets/{set_id}`

- 用途：查看规则集的默认版本和 published versions。
- 认证：Bearer JWT；兼容 legacy `X-Admin-Token`。
- 当前支持：`set_id=electronics-default`
- 响应：
  - `id`
  - `default_version`
  - `versions[]`

`versions[]` 只列出 published 版本，不列出 `draft`。

### `GET /api/v1/term-rule-sets/{set_id}/draft`

- 用途：查看当前 draft。
- 认证：Bearer JWT；兼容 legacy `X-Admin-Token`。
- 当前行为：
  - 已有 draft 时直接返回 draft
  - 没有 draft 且已有默认 published 版本时，从默认版本派生 draft
  - 没有默认 published 版本时，从当前 live store 派生 draft
- 响应：
  - `term_rule_set_id`
  - `base_version`
  - `rule_count`
  - `enabled_rule_count`
  - `yaml_text`
  - `snapshot_hash`

### `PUT /api/v1/term-rule-sets/{set_id}/draft/rules`

- 用途：用完整 v2 YAML 更新 draft。
- 认证：Bearer admin JWT；兼容 legacy `X-Admin-Token`
- 请求体：
  - `expected_snapshot_hash`：可选；用于防止基于过期 draft 覆盖最新内容
  - `yaml_text`
- 成功响应：`TermRuleSetDraftResponse`
- 关键语义：
  - 请求体必须是完整 term-rules v2 YAML
  - 只更新 resource version draft
  - 不改变当前任务使用的 runtime YAML

无效 YAML 返回 `400`，`detail` 结构：

```json
{
  "code": "invalid_term_rule_set_draft",
  "report": {
    "valid": false,
    "summary": {
      "category_count": 0,
      "rule_count": 0,
      "error_count": 1,
      "warning_count": 0
    },
    "errors": [],
    "warnings": []
  }
}
```

过期 draft snapshot 返回 `409`，`detail` 结构：

```json
{
  "code": "draft_snapshot_conflict",
  "message": "Term Rule Set draft 已被其他修改更新，请刷新后重试。",
  "expected_snapshot_hash": "client-known-hash",
  "actual_snapshot_hash": "current-draft-hash"
}
```

### `GET /api/v1/term-rule-sets/{set_id}/draft/rules`

- 用途：分页查询当前 draft 中的结构化规则。
- 认证：Bearer JWT；兼容 legacy `X-Admin-Token`；不要求 JWT 用户是 admin。
- 查询参数：
  - `page`：默认 `1`，最小 `1`
  - `page_size`：默认 `20`，范围 `1..200`
  - `category_id`：可选，按 draft 分类 ID 过滤
  - `enabled`：可选，按启用状态过滤
  - `q`：可选，按 `source_term` 子串过滤
- 成功响应：`TermRuleListResponse`
- 关键语义：
  - 数据来源是 resource version draft
  - 排序沿用 live rule 列表语义：`priority`、`source_term`
  - 不读取或刷新 runtime YAML

### `GET /api/v1/term-rule-sets/{set_id}/draft/rules/{rule_id}`

- 用途：读取当前 draft 中的一条结构化规则。
- 认证：Bearer JWT；兼容 legacy `X-Admin-Token`；不要求 JWT 用户是 admin。
- 成功响应：`TermRuleResponse`
- `rule_id` 不存在返回 `404`

### `POST /api/v1/term-rule-sets/{set_id}/draft/rules`

- 用途：向当前 draft 新增一条结构化规则。
- 认证：Bearer admin JWT；兼容 legacy `X-Admin-Token`
- 请求体：复用 `TermRuleCreateRequest`
- 成功响应：`201 TermRuleDraftRuleMutationResponse`
- 关键语义：
  - `expected_snapshot_hash` 可选；传入后服务会拒绝过期 draft 写入
  - `id` 可选；缺省时由服务生成稳定唯一 ID
  - `category_id` 必须存在于当前 draft categories
  - `source_term` 在当前 draft 内必须唯一
  - `segments` 必须非空，`render_type` 必须是支持的渲染类型
  - `custom_html` / `custom_markdown` 缺省时由 `segments` 生成
  - 只更新 draft，不改变 runtime YAML 或 published version

### `PATCH /api/v1/term-rule-sets/{set_id}/draft/rules/{rule_id}`

- 用途：局部更新当前 draft 中的一条结构化规则。
- 认证：Bearer admin JWT；兼容 legacy `X-Admin-Token`
- 请求体：复用 `TermRuleUpdateRequest`
- 成功响应：`TermRuleDraftRuleMutationResponse`
- 关键语义：
  - `expected_snapshot_hash` 可选；传入后服务会拒绝过期 draft 写入
  - `category_id` 变更时必须指向当前 draft 内存在的分类
  - `source_term` 变更后仍必须在当前 draft 内唯一
  - `segments` 变更且未显式传入 `custom_html` / `custom_markdown` 时，会按新 segments 重新生成渲染结果
  - 只更新 draft，不改变 runtime YAML 或 published version

### `DELETE /api/v1/term-rule-sets/{set_id}/draft/rules/{rule_id}`

- 用途：从当前 draft 删除一条结构化规则。
- 认证：Bearer admin JWT；兼容 legacy `X-Admin-Token`
- 查询参数：
  - `expected_snapshot_hash`：可选；用于防止基于过期 draft 删除最新内容
- 成功响应：`TermRuleDraftRuleDeleteResponse`
- 关键语义：
  - 删除只作用于 draft
  - 不删除任何 published version，不做真实文件删除，不改变 runtime YAML

### `GET /api/v1/term-rule-sets/{set_id}/diff`

- 用途：查看 draft 相对默认版本或指定 published version 的结构化差异。
- 认证：Bearer JWT；兼容 legacy `X-Admin-Token`；不要求 JWT 用户是 admin。
- 查询参数：
  - `from`：默认 `default`；支持 `default` 或 published version
  - `to`：默认 `draft`；当前仅支持 `draft`
  - `include_unchanged`：默认 `false`；为 `true` 时返回 unchanged items
- 成功响应：`TermRuleSetDiffResponse`
- 关键语义：
  - 以 `rule_id` 作为主匹配键
  - `change_type` 支持 `added`、`updated`、`disabled`、`removed`、`unchanged`
  - `disabled` 表示 base 中启用、target 中停用；其他字段变化仍会出现在 `changed_fields`
  - 默认只返回 changed items，但 summary 始终统计 unchanged
  - diff 不修改 draft、published version、默认指针或 runtime YAML

### `GET /api/v1/term-rule-sets/{set_id}/preflight`

- 用途：查看当前 draft 发布前治理校验报告。
- 认证：Bearer JWT；兼容 legacy `X-Admin-Token`；不要求 JWT 用户是 admin。
- 查询参数：
  - `base`：默认 `default`；支持 `default` 或 published version
- 成功响应：`TermRuleSetPreflightResponse`
- Blocking errors：
  - `missing_category`：规则引用不存在的分类
  - `disabled_category`：启用规则引用已禁用分类
  - `duplicate_source_term`：draft 内存在重复 source term
  - `empty_segments`：规则 segments 为空
- Warnings：
  - `default_version_drift`：draft 基线不是当前默认版本
  - `removed_rules`：本次发布会移除规则
  - `disabled_rules`：本次发布会停用规则
  - `approved_unpublished_proposals`：发布成功后会把已审核未发布 proposal 标记为本次版本
- 关键语义：
  - `blocking=true` 时 publish 会被阻止
  - warning 不阻止 publish
  - 当前 child task 预留 `conflicts[]`，proposal stale conflict 留给后续治理边界任务

### `POST /api/v1/term-rule-sets/{set_id}/import`

- 用途：导入完整 v2 YAML 到 draft 或 seed 目标。
- 认证：Bearer admin JWT；兼容 legacy `X-Admin-Token`
- 请求体字段：
  - `yaml_text`：完整 term-rules v2 YAML
  - `expected_snapshot_hash`：可选；`target=draft` 时用于防止基于过期 draft 覆盖最新内容，`target=seed` 时忽略
  - `target`：`draft` 或 `seed`，默认 `draft`
  - `dedupe`：`reject` 或 `keep_first`，默认 `reject`
- 成功响应：`TermRuleSetImportResponse`
- 审计：成功后写 `term_rule_set.import`。
- 关键语义：
  - `schema_version: 2` 与 `schema_version: 2.1` 均可导入；`2.1` 主要用于表达可逆的高级渲染字段
  - `target=draft` 只更新 resource version draft
  - `target=seed` 会作为 versioned seed 导入并同步 live runtime store 和 runtime YAML
  - `dedupe=reject` 时重复 `source_term` 会作为导入错误返回
  - `dedupe=keep_first` 时保留首次出现的规则并在 import report 中记录重复项
  - `custom_markdown` / `custom_html` 会被保留；未提供时由 `segments` 自动生成

### `GET /api/v1/term-rule-sets/{set_id}/export`

- 用途：导出规则集 draft、默认版本或指定 published version。
- 认证：Bearer admin JWT；兼容 legacy `X-Admin-Token`
- 查询参数：
  - `version`：可选；缺省导出默认版本；可传 `draft`
  - `format`：`term_rules_v2` 或 `legacy_runtime`，默认 `term_rules_v2`
- 成功响应：`TermRuleSetExportResponse`
- 审计：成功后写 `term_rule_set.export`。
- 关键语义：
  - `format=term_rules_v2` 导出规范 v2 YAML；为了兼容既有 seed，导出仍写 `schema_version: 2`
  - 与 `segments` 生成值不同的 `custom_markdown` / `custom_html` 会被写入导出 YAML，避免高级规则 round-trip 丢失自定义预览
  - `format=legacy_runtime` 导出 legacy runtime YAML
  - export 不改变 draft、published version、默认指针或 runtime YAML

### `POST /api/v1/term-rule-sets/{set_id}/publish`

- 用途：把当前 draft 发布为新的 immutable published version。
- 认证：Bearer admin JWT；兼容 legacy `X-Admin-Token`
- 请求体字段：
  - `make_default`：是否发布后设为默认，默认 `true`
  - `published_by`：可选发布人标识，仅写入 payload 元数据
  - `publish_reason`：必填发布说明，写入 payload 元数据和 audit reason
- 成功响应：`TermRuleSetVersionResponse`
- 版本号格式：`YYYY.MM.DD-N`
- 审计：成功后写 `term_rule_set.publish`，`target_id={set_id}@{version}`；`publish_reason` 同时作为 audit reason。
- 关键语义：
  - 发布前会执行 preflight；blocking errors 会阻止发布
  - `make_default=true` 时同步 live runtime store 和 runtime YAML
  - `make_default=false` 时只保存 published version，不改变默认指针和 runtime YAML
  - 发布成功后，`/api/v1/term-rule-proposals?scope=approved_unpublished` 中属于该规则集的 proposal 会写入 `published_term_rule_set_version`，避免继续显示为待发布

Preflight blocking 返回 `400`，`detail` 结构：

```json
{
  "code": "term_rule_set_preflight_failed",
  "report": {
    "valid": false,
    "blocking": true,
    "errors": [],
    "warnings": [],
    "conflicts": []
  }
}
```

### `POST /api/v1/term-rule-sets/{set_id}/versions/{version}/set-default`

- 用途：把指定 published version 设为默认版本。
- 认证：Bearer admin JWT；兼容 legacy `X-Admin-Token`
- 请求体：无
- 审计：成功后写 `term_rule_set.set_default`，`target_id={set_id}@{version}`。
- 关键语义：
  - 只能指向 published version
  - `version=draft` 会返回 `400`
  - 成功后同步 live runtime store 和 runtime YAML

### `POST /api/v1/term-rule-sets/{set_id}/rollback`

- 用途：把默认指针切回指定 published version。
- 认证：Bearer admin JWT；兼容 legacy `X-Admin-Token`
- 请求体：
  - `version`
- 审计：成功后写 `term_rule_set.rollback`，`target_id={set_id}@{version}`。
- 关键语义：
  - rollback 只切默认指针
  - 不修改任何历史 published payload
  - 成功后同步 live runtime store 和 runtime YAML

## 响应模型

### `TermRuleSetVersionResponse`

| 字段 | 说明 |
|---|---|
| `term_rule_set_id` | 规则集 ID |
| `version` | 版本号 |
| `status` | resource version 状态 |
| `rule_count` | 规则总数 |
| `enabled_rule_count` | 启用规则数 |
| `snapshot_hash` | payload hash |
| `is_default` | 是否当前默认版本 |
| `published_by` | 发布人元数据 |
| `publish_reason` | 发布原因元数据 |
| `published_at` | 发布时间元数据 |

### `TermRuleSetDraftResponse`

| 字段 | 说明 |
|---|---|
| `term_rule_set_id` | 规则集 ID |
| `base_version` | draft 派生来源版本 |
| `rule_count` | draft 规则总数 |
| `enabled_rule_count` | draft 启用规则数 |
| `yaml_text` | draft 的规范化 v2 YAML |
| `snapshot_hash` | draft payload hash |

### `TermRuleDraftRuleMutationResponse`

| 字段 | 说明 |
|---|---|
| `rule` | 新增或更新后的 `TermRuleResponse` |
| `draft` | 写入后的 `TermRuleSetDraftResponse` |

### `TermRuleDraftRuleDeleteResponse`

| 字段 | 说明 |
|---|---|
| `id` | 被删除的 draft rule ID |
| `removed` | 是否已删除 |
| `draft` | 删除后的 `TermRuleSetDraftResponse` |

### `TermRuleSetDiffResponse`

| 字段 | 说明 |
|---|---|
| `term_rule_set_id` | 规则集 ID |
| `base_ref` | 基线版本引用，包括 `ref`、`version`、`snapshot_hash`、规则数量 |
| `target_ref` | 目标版本引用，当前通常为 draft |
| `summary` | added / updated / disabled / removed / unchanged / total 计数 |
| `items` | 变化明细；默认不含 unchanged |

### `TermRuleSetDiffItemResponse`

| 字段 | 说明 |
|---|---|
| `change_type` | `added`、`updated`、`disabled`、`removed` 或 `unchanged` |
| `rule_id` | 规则 ID |
| `source_term` | 用于展示和定位的 source term |
| `category_id` | 用于展示和定位的分类 ID |
| `changed_fields` | 发生变化的规则字段 |
| `before` | 基线版本中的 `TermRuleResponse`；新增规则为 `null` |
| `after` | draft 中的 `TermRuleResponse`；移除规则为 `null` |

### `TermRuleSetPreflightResponse`

| 字段 | 说明 |
|---|---|
| `term_rule_set_id` | 规则集 ID |
| `valid` | 是否没有 blocking errors/conflicts |
| `blocking` | 是否会阻止 publish |
| `base_ref` | 校验基线版本 |
| `draft_ref` | 当前 draft 引用 |
| `summary` | error / warning / conflict 数量和 draft 规模 |
| `errors` | blocking errors |
| `warnings` | 非阻断告警 |
| `conflicts` | 预留结构化冲突列表 |
| `diff_summary` | 同一基线下的 diff summary |

### `TermRuleGovernanceFindingResponse`

| 字段 | 说明 |
|---|---|
| `severity` | `error`、`warning` 或 `conflict` |
| `code` | 稳定 finding code |
| `message` | 面向用户的说明 |
| `path` | 可选定位路径 |
| `rule_id` | 可选规则 ID |
| `source_term` | 可选 source term |
| `category_id` | 可选分类 ID |
| `metadata` | 可选结构化附加信息 |

### `TermRuleSetImportResponse`

| 字段 | 说明 |
|---|---|
| `target` | 导入目标：`draft` 或 `seed` |
| `term_rule_set_id` | 规则集 ID |
| `version` | 导入后对应的 draft 或 seed 版本 |
| `rule_count` | 导入后规则总数 |
| `enabled_rule_count` | 导入后启用规则数 |
| `snapshot_hash` | 导入后 payload hash |
| `validation` | YAML 校验报告 |
| `import_report` | 去重和导入统计报告 |

### `TermRuleSetExportResponse`

| 字段 | 说明 |
|---|---|
| `manifest` | 导出元数据，包括 `set_id`、`version`、`format`、`exported_at`、`exported_by` |
| `yaml_text` | 导出的 YAML 文本 |

## 常见状态

- `400`：YAML 无效、版本状态不允许、`set_id` 格式非法、draft rule 字段非法、重复 `source_term`、preflight blocking，或尝试把 draft 设为默认
- `403`：admin-only 写接口缺少或未通过 Bearer admin JWT / legacy `X-Admin-Token`
- `404`：规则集、目标版本、draft rule 或 draft category 不存在
- `503`：未启用 MySQL resource service

## 相关条目

- [term-rules.md](/Users/sc/PycharmProjects/md2word/docs/api/term-rules.md)
- [term-rule-categories.md](/Users/sc/PycharmProjects/md2word/docs/api/term-rule-categories.md)
- [templates.md](/Users/sc/PycharmProjects/md2word/docs/api/templates.md)
