---
doc_type: lib-api-ref
entry: templates
category: endpoint
status: current
source_files:
  - app/api/v1/router.py
  - app/api/v1/routers/templates.py
  - app/services/templates/read_service.py
  - app/schemas/api_v1.py
summary: Templates API 提供多模板清单、详情、下载和默认模板切换；模板资产仍来自版本化 manifest。
tags: [templates, api, manifest]
last_reviewed: 2026-05-18
---

## 概述

当前 Templates API 统一挂在 `/api/v1/templates` 下，模板资产来自版本化
manifest，运行态只记录“当前默认模板”：

- 模板列表
- 单个模板详情
- 模板文件下载
- 默认模板切换

这一阶段不提供模板 CRUD，也不通过 API 直接返回 YAML 内容。目标是让
前端看见多模板、下载模板，并让 jobs 能引用显式 `template_id`。

## API 参考

### `GET /api/v1/templates`

- 用途：列出当前可用模板。
- 当前行为：
  - 返回 manifest 中全部可见且启用的模板
  - 每项同时带出：
    - 模板文件元数据
    - `datasheet_template.yaml` 元数据
    - 当前运行态术语 YAML 元数据

- 响应关键字段：
  - `items[].id`
  - `items[].name`
  - `items[].is_default`
  - `items[].downloadable`
  - `items[].download_url`
  - `items[].template`
  - `items[].layout_config`
  - `items[].subscript_config`

### `GET /api/v1/templates/{template_id}`

- 用途：查询单个模板详情。
- 当前支持：
  - 任意 manifest 中可见且启用的 `template_id`

- 资产元数据字段：

| 字段 | 说明 |
|---|---|
| `label` | 资产中文标签 |
| `exists` | 是否存在 |
| `file_name` | 文件名 |
| `size_bytes` | 文件大小 |
| `updated_at` | 最后修改时间 |
| `sha256` | 文件内容摘要 |
| `download_url` | 下载地址；目前仅模板文件有 |

### `GET /api/v1/templates/{template_id}/download`

- 用途：下载指定模板文件。

### `PATCH /api/v1/templates/{template_id}/default`

- 用途：将指定模板设为当前运行态默认模板。
- 认证：`X-Admin-Token`
- 关键语义：
  - 不改模板 manifest
  - 只改运行态 default state
  - jobs 未显式传 `template_id` 时，后续将回退到这个默认模板

- 常见状态：
  - `404`：模板 ID 不存在，或默认模板文件缺失

## 当前限制

- 不支持创建、更新、启停、替换或删除模板。
- layout/subscript YAML 只返回元数据，不返回原始内容。
- 模板清单来自版本化 manifest，不是运行态可写库存。
