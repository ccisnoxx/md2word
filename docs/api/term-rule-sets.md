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
summary: Term-rule-sets API 在 MySQL resource service 下提供术语规则集 draft、publish、set-default、rollback 和成功动作审计。
tags: [term-rules, resource-versioning, api, audit]
last_reviewed: 2026-05-31
---

## 概述

当前 `term-rule-sets` 统一挂在 `/api/v1/term-rule-sets` 下，用于管理术语规则集的草稿、发布版本、默认指针和回滚。

当前约束：

- 需要 `JOBS_REPOSITORY_BACKEND=mysql`，否则接口返回 `503`
- MVP 只支持默认规则集 `electronics-default`
- draft 更新不写 `term_rules_store.json`，也不刷新 `runtime_subscripts_dictionary.yaml`
- publish / set-default / rollback 只有目标版本成为默认 published 版本时，才同步 legacy live runtime store 和 runtime YAML
- MySQL versioned mode 下，legacy `/term-rules` 和 `/term-rule-categories` 写接口会拒绝直写
- publish / set-default / rollback 成功后会写 audit event

## API 参考

### `GET /api/v1/term-rule-sets`

- 用途：列出当前支持的术语规则集。
- 前置：需要 MySQL resource service。
- 响应：
  - `items[].id`
  - `items[].default_version`
  - `items[].version_count`
  - `items[].rule_count`
  - `items[].enabled_rule_count`

### `GET /api/v1/term-rule-sets/{set_id}`

- 用途：查看规则集的默认版本和 published versions。
- 当前支持：`set_id=electronics-default`
- 响应：
  - `id`
  - `default_version`
  - `versions[]`

`versions[]` 只列出 published 版本，不列出 `draft`。

### `GET /api/v1/term-rule-sets/{set_id}/draft`

- 用途：查看当前 draft。
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
- 认证：`X-Admin-Token`
- 请求体：
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

### `POST /api/v1/term-rule-sets/{set_id}/publish`

- 用途：把当前 draft 发布为新的 immutable published version。
- 认证：`X-Admin-Token`
- 请求体字段：
  - `make_default`：是否发布后设为默认，默认 `true`
  - `published_by`：可选发布人标识，仅写入 payload 元数据
  - `publish_reason`：可选发布原因，仅写入 payload 元数据
- 成功响应：`TermRuleSetVersionResponse`
- 版本号格式：`YYYY.MM.DD-N`
- 审计：成功后写 `term_rule_set.publish`，`target_id={set_id}@{version}`；`publish_reason` 同时作为 audit reason。
- 关键语义：
  - `make_default=true` 时同步 live runtime store 和 runtime YAML
  - `make_default=false` 时只保存 published version，不改变默认指针和 runtime YAML

### `POST /api/v1/term-rule-sets/{set_id}/versions/{version}/set-default`

- 用途：把指定 published version 设为默认版本。
- 认证：`X-Admin-Token`
- 请求体：无
- 审计：成功后写 `term_rule_set.set_default`，`target_id={set_id}@{version}`。
- 关键语义：
  - 只能指向 published version
  - `version=draft` 会返回 `400`
  - 成功后同步 live runtime store 和 runtime YAML

### `POST /api/v1/term-rule-sets/{set_id}/rollback`

- 用途：把默认指针切回指定 published version。
- 认证：`X-Admin-Token`
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

## 常见状态

- `400`：YAML 无效、版本状态不允许、`set_id` 格式非法，或尝试把 draft 设为默认
- `403`：admin-only 写接口缺少或未通过 `X-Admin-Token`
- `404`：规则集不存在，或目标版本不存在
- `503`：未启用 MySQL resource service

## 相关条目

- [term-rules.md](/Users/sc/PycharmProjects/md2word/docs/api/term-rules.md)
- [term-rule-categories.md](/Users/sc/PycharmProjects/md2word/docs/api/term-rule-categories.md)
- [templates.md](/Users/sc/PycharmProjects/md2word/docs/api/templates.md)
