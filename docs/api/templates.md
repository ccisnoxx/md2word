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
doc_status: active
last_verified_commit: null
owner: null
verification_scope: >-
  全文用途与当前 v1 挂载/声明入口的局部静态核对；未逐字段认证 schema、权限、副作用或真实请求。工作区内容身份及旧说明差异见 ../../.trellis/tasks/archive/2026-11/11-10-documentation-evidence-governance/research/b3-preparation.md。
---

## 概述

本页维护模板文档、版式草稿与资源版本的 API 参考。本批仅静态核对路由挂载与声明入口，未逐字段复核响应、权限、副作用或真实请求；示例和原验收声明仍按各自记录范围解释。

Templates API 统一挂在 `/api/v1/templates` 下。MySQL 模式以数据库目录和版本快照为准，bundled manifest 只用于只读初始化。上传的 DOCX 保存在 `TEMPLATES_STORAGE_PATH` 指向的共享受管目录。

- 模板列表
- 单个模板详情
- 模板文件下载
- 默认模板切换
- 模板创建、元数据更新、删除
- 模板 DOCX 替换和版本查看
- 版式配置读取和保存为 draft version
- Template Version 创建、发布、设默认和禁用

模板管理写入需要 admin 权限。创建、更新、替换、删除、默认切换和版本发布、禁用等成功操作均沿用各自的审计事件。

## API 参考

### `GET /api/v1/templates`

- 用途：列出当前可用模板。
- 当前行为：
  - 返回当前目录中启用且未删除的模板
  - 每项同时带出：
    - 模板文件元数据
    - 返回的模板版本所绑定的版式 YAML 元数据
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
  - 任意启用且未删除的 `template_id`

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

- 用途：列出模板的版本与状态。MySQL 以已登记记录为准，登记的文件缺失时资产显示 `exists=false`。
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

- 成功后 `version=1`。MySQL 同时登记模板目录和首版 draft；通过验证并发布后，普通任务才能选择该版本。

### `PATCH /api/v1/templates/{template_id}`

- 用途：更新模板元数据。
- 认证：Bearer admin JWT；兼容 legacy `X-Admin-Token`
- 请求体：JSON，可选字段：
  - `name`
  - `description`
  - `enabled`
  - `layout_config_path`
  - `render_policy`
- MySQL 的版式路径和渲染策略更新只影响后续上传的缺省配置。已登记版本继续使用原快照。

### `PUT /api/v1/templates/{template_id}/file`

- 用途：替换模板 DOCX 文件。
- 认证：Bearer admin JWT；兼容 legacy `X-Admin-Token`
- 请求体：`multipart/form-data`
  - `template`: `.docx` 文件
- MySQL 模式创建新 draft，原默认版本和旧版本文件保留。file/SQLite 沿用原本地版本切换。

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
  - MySQL 目录模式还要求任务的模板资源快照绑定同一个 draft 及其 SHA-256
- 成功响应会返回 `verification_job_id`、`verification_note`、`verified_by`、`verified_at`、`publish_reason`、`published_by`、`published_at`。

### `POST /api/v1/templates/{template_id}/versions/{version}/set-default`

- 用途：把指定已发布版本设为当前默认模板版本。
- 认证：Bearer admin JWT；兼容 legacy `X-Admin-Token`
- 请求体：JSON
  - `set_default_reason`: 必填，切换原因
- 审计：指针和 `template.set_default` 在同一 MySQL 事务提交，`target_id={template_id}@{version}`，`set_default_reason` 写入审计理由。
- 关键语义：
  - 切换前预检已登记的 DOCX 和已绑定 YAML，比对实际 SHA-256。
  - MySQL `resource_default_versions` 是每个模板的默认版本指针唯一来源。事务按旧指针及目标快照比较写入，并读回确认。
  - 此接口只切换指定 `template_id` 的默认版本。切换全局默认模板 ID 使用 `PATCH /api/v1/templates/{template_id}/default`。
  - 后续按该模板创建任务时固化其默认版本，Worker 使用同版本的登记资源。
- 常见错误：
  - `400` 表示目标状态或登记资源未通过校验。文件问题通过 `error.reason_code` 给出具体原因，原指针保留。
  - `409` 与 `template_default_conflict` 表示指针或目标状态、快照已变化。重新读取版本列表后再决定是否发起切换。
  - `503` 与 `template_default_commit_unknown` 表示数据库提交结果无法确认。先读取版本列表核对实际默认版本，再决定后续操作。

### `POST /api/v1/templates/{template_id}/versions/{version}/disable`

- 用途：禁用非默认模板版本。
- 认证：Bearer admin JWT；兼容 legacy `X-Admin-Token`
- 审计：成功后写 `template.disable`，`target_id={template_id}@{version}`。
- 约束：
  - 默认版本不能直接禁用
  - 历史 DOCX 文件保留。仍未渲染的已绑定任务会被 Worker 拒绝，失败原因码为 `resource_snapshot_invalid_status`

### `PATCH /api/v1/templates/{template_id}/default`

- 用途：将指定模板设为当前运行态默认模板。
- 认证：Bearer admin JWT；兼容 legacy `X-Admin-Token`
- 关键语义：
  - MySQL 更新数据库全局默认模板 ID。目标必须已启用，且有可用的已发布默认版本
  - 后续未显式选择模板的任务使用此默认模板。file/SQLite 继续使用 `template_state.json`

- 常见状态：
  - `404` 表示模板不存在或未启用。在 file/SQLite 模式下也包括模板文件缺失
  - `400` 表示 MySQL 模式下缺少可用的已发布默认版本，或资源包校验失败
  - `409` 表示检查完成后该模板的默认版本已发生变化
  - `503 template_catalog_commit_unknown` 表示提交结果需要重新读取目录确认

### `DELETE /api/v1/templates/{template_id}`

- 用途：从可选模板目录移除模板。MySQL 保留删除状态与历史版本。
- 认证：Bearer admin JWT；兼容 legacy `X-Admin-Token`
- 约束：
  - 当前默认模板不能删除
  - 模板级停用或删除后，不能新建或克隆任务来绑定该模板。已绑定快照的同一任务仍能按原版本执行或重试，Worker 继续校验版本状态与资源哈希
  - 历史版本文件保留

## 当前限制

- subscript YAML 仍只返回元数据，不返回原始内容。
- 版式配置页面只编辑 `template-config/v1` 白名单字段；`schema_version`、`template_name`、`output_filename`、`sample_content`、隐藏 renderer 字段和 A4 页面宽高不开放编辑。
- 浏览器预览是近似效果；发布前必须创建绑定该 draft 的真实 Word 验证任务。
- Template Version 发布管理只在 MySQL metadata backend 下启用；file / sqlite backend 保持 manifest 兼容路径。
- MySQL resource mode 下，jobs 创建已支持 `template_version` 快照；不传时绑定当前默认 Template Version。
- file / sqlite backend 下，jobs 显式传 `template_version` 会返回 `503`，只传 `template_id` 仍走 legacy 模板选择路径。
