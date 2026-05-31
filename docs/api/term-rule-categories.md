---
doc_type: lib-api-ref
entry: term-rule-categories
category: endpoint
status: current
source_files:
  - app/api/v1/router.py
  - app/domains/term_rules/categories_router.py
  - app/domains/term_rules/write_guard.py
  - app/domains/term_rules/service.py
  - app/domains/term_rules/file_repository.py
  - app/domains/term_rules/schemas.py
summary: Term-rule-categories API 提供分类元数据、规则计数和分类增量写接口；MySQL versioned mode 下写入交给 Term Rule Set 发布流程。
tags: [term-rules, categories, api]
last_reviewed: 2026-05-31
---

## 概述

当前 `term-rule-categories` 是术语分类资源，统一挂在
`/api/v1/term-rule-categories` 下。

它的职责是：

- 给前端提供稳定的分类列表
- 提供分类级优先级、启停状态和说明
- 提供每个分类下的规则数量统计
- 提供分类创建、更新和删除能力

当 MySQL resource service 启用 Term Rule Set versioning 时，分类写接口会返回 `400`，调用方应改用 `/api/v1/term-rule-sets/{set_id}/draft/rules` 提交完整规则集草稿并发布。

## API 参考

### `GET /api/v1/term-rule-categories`

- 用途：列出全部分类及规则计数。
- 响应字段：
  - `items[].id`
  - `items[].code`
  - `items[].name`
  - `items[].priority`
  - `items[].enabled`
  - `items[].description`
  - `items[].rule_count`
  - `items[].enabled_rule_count`

### `POST /api/v1/term-rule-categories`

- 用途：新增术语分类。
- 认证：`X-Admin-Token`
- 请求体字段：
  - `id`：可选；不传时自动生成
  - `code`：英文稳定标识，格式与 v2 YAML 分类 code 一致
  - `name`
  - `priority`
  - `enabled`
  - `description`
- MySQL versioned mode 下返回 `400`，避免绕过 Term Rule Set draft / publish。

### `PATCH /api/v1/term-rule-categories/{category_id}`

- 用途：更新术语分类。
- 认证：`X-Admin-Token`
- 请求体为 `code/name/priority/enabled/description` 的任意子集。
- MySQL versioned mode 下返回 `400`，避免绕过 Term Rule Set draft / publish。

### `DELETE /api/v1/term-rule-categories/{category_id}`

- 用途：删除术语分类。
- 认证：`X-Admin-Token`
- 约束：分类下仍有规则时不能删除；需要先删除或迁移规则。
- MySQL versioned mode 下返回 `400`，避免绕过 Term Rule Set draft / publish。

## 相关条目

- [term-rule-sets.md](/Users/sc/PycharmProjects/md2word/docs/api/term-rule-sets.md)
- [term-rules.md](/Users/sc/PycharmProjects/md2word/docs/api/term-rules.md)
