---
doc_type: lib-api-ref
entry: term-rule-categories
category: endpoint
status: current
source_files:
  - app/api/v1/router.py
  - app/api/v1/routers/term_rule_categories.py
  - app/services/term_rules/service.py
  - app/repositories/file_term_rule_repository.py
  - app/schemas/api_v1.py
summary: Term-rule-categories API 提供只读分类元数据与规则计数，用于筛选、展示和导入校验辅助。
tags: [term-rules, categories, api, readonly]
last_reviewed: 2026-05-18
---

## 概述

当前 `term-rule-categories` 是轻量只读资源，统一挂在
`/api/v1/term-rule-categories` 下。

它的职责是：

- 给前端提供稳定的分类列表
- 提供分类级优先级、启停状态和说明
- 提供每个分类下的规则数量统计

这一阶段不提供分类 CRUD。

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
