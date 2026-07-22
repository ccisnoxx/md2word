---
doc_type: lib-api-ref
entry: templates
category: endpoint
status: current
source_files:
  - app/api/v1/router.py
  - app/domains/templates/router.py
  - app/api/dependencies.py
  - app/domains/audit/models.py
  - app/domains/audit/service.py
  - app/domains/templates/read_service.py
  - app/domains/templates/layout_config_schema.py
  - app/domains/resources/service.py
  - app/domains/templates/schemas.py
summary: Templates API 提供多模板清单、详情、下载、默认模板切换、模板 CRUD、文件替换、版式配置 draft version、Template Version 发布管理和成功动作审计。
tags: [templates, api, manifest, audit]
last_reviewed: 2026-07-11
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
- 版式配置读取和保存为 draft version
- Template Version 创建、发布、设默认和禁用

Template Version 的 publish / set-default / disable 和版式配置 draft 创建成功路径会写入 audit event。普通模板 CRUD 和旧运行态默认模板切换目前只保留 admin 鉴权，不写 audit event。

## API 参考

### `GET /api/v1/templates`

- 用途：列出当前可用模板。
- 当前行为：
  - 返回 manifest 中全部可见且启用的模板
  - 每项同时带出：
    - 模板文件元数据
    - manifest 当前绑定的版式 YAML 元数据
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
- 认证：Bearer admin JWT；兼容 legacy `X-Admin-Token`。
- 响应：
  - `template_id`
  - `items[].version`
  - `items[].status`
  - `items[].is_current`
  - `items[].is_default`
  - `items[].snapshot_hash`
  - `items[].render_policy`
  - `items[].verification_job_id`
  - `items[].verification_note`
  - `items[].verified_by`
  - `items[].verified_at`
  - `items[].template`
  - `items[].layout_config`

### `GET /api/v1/templates/{template_id}/layout-config?version={version}`

- 用途：Admin-only 读取默认或指定 Template Version 绑定的 Word 版式配置，用于可视化样式管理页。
- 认证：Bearer admin JWT；兼容 legacy `X-Admin-Token`
- 查询参数：`version` 可选；不传时读取数据库默认 published version，传入时可读取 draft/published 历史版本。
- 响应：
  - `template_id`
  - `template_version_id`
  - `version`
  - `status`、`is_default`、`active_template_version_id`
  - `source_path`：仅返回仓库内相对路径；服务器外部路径返回 `null`
  - `config_sha256`
  - `snapshot_hash`
  - `meta`：只读元信息，例如 `schema_version`、`template_name`、`output_filename`
  - `config`：18 个一级样式分组的规范化值；不包含 `meta`、`sample_content` 和隐藏 renderer 字段
  - `preview_samples`：只读浏览器近似预览样例
  - `field_schema`：唯一前端表单合同，包含有序 `categories`、中文 `group_meta`、字段类型、标签、单位、范围、选项和只读属性

### `POST /api/v1/templates/{template_id}/layout-config/versions`

- 用途：Admin-only 将页面提交的版式配置保存为新的 Template Profile draft version。
- 认证：Bearer admin JWT；兼容 legacy `X-Admin-Token`
- 前置：需要 `JOBS_REPOSITORY_BACKEND=mysql`，因为 draft / publish 状态由 `ResourceVersionService` 管理。
- 请求体：JSON

```json
{
  "base_template_version_id": "default@1",
  "expected_config_sha256": "sha256:...",
  "expected_active_template_version_id": "default@1",
  "changes": {"normal": {"font_size": 11}},
  "change_note": "调整正文字号"
}
```

- 行为：
  - 只接受 `layout_config_schema.py` 声明的可编辑叶子字段；拒绝完整 YAML、未知字段、只读字段和 `sample_content`
  - 用 base version + config hash + active version 做并发校验，不自动合并冲突
  - 从 exact base 合并 dirty patch，并重新执行完整 `template-config/v1`、数值范围、页面边距和 DOCX 表格样式校验
  - 在同文件系统 staging 目录复制 DOCX、写入并 fsync `layout_config.yaml`，校验成功后原子 rename
  - 通过 MySQL 序列分配不复用的整数版本，并以 create-only 语义写入 Resource Version draft
  - 创建 `TemplateVersionResponse(status="draft")`
  - 不修改 manifest 绑定的仓库内 seed YAML
  - 不自动发布，也不替换当前默认模板
- 审计：成功后写 `template.layout_config_version_create`，`target_id={template_id}@{version}`。
- 错误：
  - `409`：active version 或 base hash 已变化；响应带当前 `active_template_version_id` 和 `config_sha256`
  - `422`：白名单、字段类型、范围、跨字段或 Word 样式校验失败；响应带 `field_errors[].path/code/message`
  - `503`：MySQL 版本服务或文件原子持久化不可用

### `POST /api/v1/templates`

- 用途：创建模板记录并上传第一个 DOCX 文件。
- 认证：Bearer admin JWT；兼容 legacy `X-Admin-Token`
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
- 认证：Bearer admin JWT；兼容 legacy `X-Admin-Token`
- 请求体：JSON，可选字段：
  - `name`
  - `description`
  - `enabled`
  - `layout_config_path`
  - `render_policy`

### `PUT /api/v1/templates/{template_id}/file`

- 用途：替换模板 DOCX 文件。
- 认证：Bearer admin JWT；兼容 legacy `X-Admin-Token`
- 请求体：`multipart/form-data`
  - `template`: `.docx` 文件
- 成功后当前 `version` 递增，旧版本文件保留。

### `POST /api/v1/templates/{template_id}/versions`

- 用途：为已有 Template Profile 上传下一版 DOCX 并创建 draft 版本。
- 认证：Bearer admin JWT；兼容 legacy `X-Admin-Token`
- 前置：需要 `JOBS_REPOSITORY_BACKEND=mysql`，因为发布状态由 `ResourceVersionService` 管理。
- 请求体：`multipart/form-data`
  - `template`: `.docx` 文件
  - `layout_config_path`: 可选
  - `render_policy_json`: 可选 JSON object
- 成功后返回 `TemplateVersionResponse(status="draft")`，不自动替换当前默认版本。

### `POST /api/v1/templates/{template_id}/versions/{version}/publish`

- 用途：发布 draft 模板版本。
- 认证：Bearer admin JWT；兼容 legacy `X-Admin-Token`
- 审计：成功后写 `template.publish`，`target_id={template_id}@{version}`，`publish_reason` 写入 audit reason。
- 请求体：JSON
  - `make_default`: 是否发布后同时设为默认版本，默认 `false`
  - `publish_reason`: 必填，发布原因
  - `verification_job_id`: 必填，验证任务 ID
  - `verification_note`: 必填，验证说明
- 发布校验：
  - `verification_job_id` 必须对应已存在的 Document Job
  - 验证任务 `status` 必须是 `succeeded`
  - 验证任务 `template_version_id` 必须匹配 `{template_id}@{version}`
- 成功响应会返回 `verification_job_id`、`verification_note`、`verified_by`、`verified_at`、`publish_reason`、`published_by`、`published_at`。

### `POST /api/v1/templates/{template_id}/versions/{version}/set-default`

- 用途：把指定已发布版本设为当前默认模板版本。
- 认证：Bearer admin JWT；兼容 legacy `X-Admin-Token`
- 请求体：JSON
  - `set_default_reason`: 必填，切换原因
- 审计：成功后写 `template.set_default`，`target_id={template_id}@{version}`，`set_default_reason` 写入 audit reason。
- 关键语义：
  - 只切资源版本默认指针，不改历史版本内容
  - MySQL `resource_default_versions` 是模板版本默认指针唯一来源
  - `template_state.json` 只保存默认 template id；manifest 不再被版本切换改写
  - 后续 job 创建时固化该 published version，Worker 严格使用同版本 DOCX 和 YAML

### `POST /api/v1/templates/{template_id}/versions/{version}/disable`

- 用途：禁用非默认模板版本。
- 认证：Bearer admin JWT；兼容 legacy `X-Admin-Token`
- 审计：成功后写 `template.disable`，`target_id={template_id}@{version}`。
- 约束：
  - 默认版本不能直接禁用
  - 历史 DOCX 文件保留，不在禁用接口中物理清理

### `PATCH /api/v1/templates/{template_id}/default`

- 用途：将指定模板设为当前运行态默认模板。
- 认证：Bearer admin JWT；兼容 legacy `X-Admin-Token`
- 关键语义：
  - 不改模板 manifest
  - 只改运行态 default state
  - jobs 未显式传 `template_id` 时，后续将回退到这个默认模板

- 常见状态：
  - `404`：模板 ID 不存在，或默认模板文件缺失

### `DELETE /api/v1/templates/{template_id}`

- 用途：从 manifest 删除模板记录。
- 认证：Bearer admin JWT；兼容 legacy `X-Admin-Token`
- 约束：
  - 当前默认模板不能删除
  - 历史版本文件保留，不在删除接口中物理清理

## 当前限制

- subscript YAML 仍只返回元数据，不返回原始内容。
- 版式配置页面只编辑 `template-config/v1` 白名单字段；`schema_version`、`template_name`、`output_filename`、`sample_content`、隐藏 renderer 字段和 A4 页面宽高不开放编辑。
- 浏览器预览是近似效果；发布前必须创建绑定该 draft 的真实 Word 验证任务。
- Template Version 发布管理只在 MySQL metadata backend 下启用；file / sqlite backend 保持 manifest 兼容路径。
- MySQL resource mode 下，jobs 创建已支持 `template_version` 快照；不传时绑定当前默认 Template Version。
- file / sqlite backend 下，jobs 显式传 `template_version` 会返回 `503`，只传 `template_id` 仍走 legacy 模板选择路径。
