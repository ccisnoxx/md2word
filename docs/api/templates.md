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
summary: Templates API 提供默认 DOCX 模板和绑定渲染配置的只读元数据与下载能力。
tags: [templates, api, readonly]
last_reviewed: 2026-05-18
---

## 概述

当前 Templates API 统一挂在 `/api/v1/templates` 下，只提供只读能力：

- 模板列表
- 单个模板详情
- 默认模板文件下载

这一阶段不提供模板 CRUD，也不通过 API 直接返回 YAML 内容。目标只是暴露默认模板、页面布局 YAML、术语上下标 YAML 的存在性和版本元数据。

## API 参考

### `GET /api/v1/templates`

- 用途：列出当前可用模板。
- 当前行为：
  - 只返回一个默认模板条目，`id=default`
  - 每项同时带出：
    - 模板文件元数据
    - `datasheet_template.yaml` 元数据
    - `subscripts_dictionary.yaml` 元数据

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
- 当前只支持：
  - `template_id=default`

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

- 用途：下载默认模板文件。
- 当前只支持：
  - `template_id=default`

- 常见状态：
  - `404`：模板 ID 不存在，或默认模板文件缺失

## 当前限制

- 只读，不支持创建、更新、启停或替换模板。
- layout/subscript YAML 只返回元数据，不返回原始内容。
- 目前只支持单一默认模板，不支持多模板切换。
