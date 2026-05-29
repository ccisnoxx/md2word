---
doc_type: lib-api-ref
entry: templates
category: endpoint
status: current
source_files:
  - app/api/v1/router.py
  - app/api/v1/routers/templates.py
  - app/api/dependencies.py
  - app/core/audit_models.py
  - app/services/audit.py
  - app/services/templates/read_service.py
  - app/services/resource_versions/service.py
  - app/schemas/templates.py
  - app/schemas/api_v1.py
summary: Templates API 提供多模板清单、详情、下载、默认模板切换、模板 CRUD、文件替换、Template Version 发布管理和成功动作审计。
tags: [templates, api, manifest, audit]
last_reviewed: 2026-05-29
---

## 概述

当前 Templates API 统一挂在 `/api/v1/templates` 下，模板资产由 manifest
记录，API 管理上传的 DOCX 会保存到 `TEMPLATES_STORAGE_PATH` 指向的版本目录：

- 模板列表
- 单个模板详情
- 模板文件下载
- 默认模板切换
- 模板创建、元数据更新、删除
- 模板 DOCX 替换和版本查看
- Template Version 创建、发布、设默认和禁用

Template Version 的 publish / set-default / disable 成功路径会写入 audit event。普通模板 CRUD 和旧运行态默认模板切换目前只保留 admin 鉴权，不写 audit event。

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
  - `items[].version`
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

### `GET /api/v1/templates/{template_id}/versions`

- 用途：列出 API 管理目录中保留的模板文件版本和资源版本状态。
- 响应：
  - `template_id`
  - `items[].version`
  - `items[].status`
  - `items[].is_current`
  - `items[].is_default`
  - `items[].snapshot_hash`
  - `items[].render_policy`
  - `items[].template`
  - `items[].layout_config`

### `POST /api/v1/templates`

- 用途：创建模板记录并上传第一个 DOCX 文件。
- 认证：`X-Admin-Token`
- 请求体：`multipart/form-data`

| 参数 | 必填 | 说明 |
|---|---|---|
| `template_id` | 是 | 稳定模板 ID，只允许字母、数字、下划线、短横线和英文句点 |
| `name` | 是 | 展示名 |
| `description` | 否 | 描述 |
| `enabled` | 否 | 是否启用，默认 `true` |
| `layout_config_path` | 否 | 绑定页面布局 YAML 路径 |
| `render_policy_json` | 否 | JSON object；默认 `{}` |
| `template` | 是 | `.docx` 文件 |

- 成功后 `version=1`，文件保存到版本目录。

### `PATCH /api/v1/templates/{template_id}`

- 用途：更新模板元数据。
- 认证：`X-Admin-Token`
- 请求体：JSON，可选字段：
  - `name`
  - `description`
  - `enabled`
  - `layout_config_path`
  - `render_policy`

### `PUT /api/v1/templates/{template_id}/file`

- 用途：替换模板 DOCX 文件。
- 认证：`X-Admin-Token`
- 请求体：`multipart/form-data`
  - `template`: `.docx` 文件
- 成功后当前 `version` 递增，旧版本文件保留。

### `POST /api/v1/templates/{template_id}/versions`

- 用途：为已有 Template Profile 上传下一版 DOCX 并创建 draft 版本。
- 认证：`X-Admin-Token`
- 前置：需要 `JOBS_REPOSITORY_BACKEND=mysql`，因为发布状态由 `ResourceVersionService` 管理。
- 请求体：`multipart/form-data`
  - `template`: `.docx` 文件
  - `layout_config_path`: 可选
  - `render_policy_json`: 可选 JSON object
- 成功后返回 `TemplateVersionResponse(status="draft")`，不自动替换当前默认版本。

### `POST /api/v1/templates/{template_id}/versions/{version}/publish`

- 用途：发布 draft 模板版本。
- 认证：`X-Admin-Token`
- 审计：成功后写 `template.publish`，`target_id={template_id}@{version}`。
- 请求体：JSON，可选字段：
  - `make_default`: 是否发布后同时设为默认版本，默认 `false`

### `POST /api/v1/templates/{template_id}/versions/{version}/set-default`

- 用途：把指定已发布版本设为当前默认模板版本。
- 认证：`X-Admin-Token`
- 审计：成功后写 `template.set_default`，`target_id={template_id}@{version}`。
- 关键语义：
  - 只切资源版本默认指针，不改历史版本内容
  - 同步 manifest 当前 `version` 和 `template_state.json`，让现有 conversion path 使用该 DOCX

### `POST /api/v1/templates/{template_id}/versions/{version}/disable`

- 用途：禁用非默认模板版本。
- 认证：`X-Admin-Token`
- 审计：成功后写 `template.disable`，`target_id={template_id}@{version}`。
- 约束：
  - 默认版本不能直接禁用
  - 历史 DOCX 文件保留，不在禁用接口中物理清理

### `PATCH /api/v1/templates/{template_id}/default`

- 用途：将指定模板设为当前运行态默认模板。
- 认证：`X-Admin-Token`
- 关键语义：
  - 不改模板 manifest
  - 只改运行态 default state
  - jobs 未显式传 `template_id` 时，后续将回退到这个默认模板

- 常见状态：
  - `404`：模板 ID 不存在，或默认模板文件缺失

### `DELETE /api/v1/templates/{template_id}`

- 用途：从 manifest 删除模板记录。
- 认证：`X-Admin-Token`
- 约束：
  - 当前默认模板不能删除
  - 历史版本文件保留，不在删除接口中物理清理

## 当前限制

- layout/subscript YAML 仍只返回元数据，不返回原始内容。
- Template Version 发布管理只在 MySQL metadata backend 下启用；file / sqlite backend 保持 manifest 兼容路径。
- MySQL resource mode 下，jobs 创建已支持 `template_version` 快照；不传时绑定当前默认 Template Version。
- file / sqlite backend 下，jobs 显式传 `template_version` 会返回 `503`，只传 `template_id` 仍走 legacy 模板选择路径。
