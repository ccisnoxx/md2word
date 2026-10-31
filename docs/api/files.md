---
doc_type: lib-api-ref
entry: files
category: endpoint
status: current
source_files:
  - app/api/v1/router.py
  - app/domains/files/router.py
  - app/domains/files/schemas.py
  - app/domains/files/models.py
  - app/domains/files/cleanup_lock.py
  - app/domains/files/library_search.py
  - app/domains/files/retention.py
  - app/domains/files/cleanup_execution.py
  - app/domains/files/cleanup_history.py
  - app/domains/files/scheduled_cleanup.py
  - app/domains/files/quota_policy.py
  - app/domains/files/storage_usage.py
  - app/domains/files/service.py
summary: Files API 提供 PDF 上传授权、后端代理上传、文件 metadata 查询、Admin-only 文件库搜索、metadata 保留期管理、quota policy dry-run、受保护的过期文件物理删除、signed cleanup run 执行合同、手动 scheduler dry-run 和 durable run history。
tags: [files, api, pdf, upload, retention, search, quota]
last_reviewed: 2026-06-07
---

## 概述

Files API 挂在 `/api/v1/files` 下，当前只面向登录用户。P0 PDF -> Word 流程先通过它登记并上传 PDF，再把返回的 `file_id` 传给 `/api/v1/document-jobs`。

Admin 文件库搜索只返回 `document_files` 安全摘要，用于定位文件和衔接现有 selected-file 运维流程。搜索结果不暴露 `object_key`、`bucket`、checksum、etag、raw metadata、本地路径、文件内容或签名 URL。

保留期管理接口只面向 Admin，用于管理保留策略、查看或标记过期 metadata，并在显式 dry-run 后人工执行本地过期文件物理删除。cleanup run 执行合同复用同一 physical-delete primitive，并额外要求 preview hash、signed cleanup plan、reason 和确认短语。preview/execute 会写入 durable run history，只保存 `run_id`、signed plan、状态、摘要计数、safety flags 和人工 reason，不保存本地路径、文件内容、bucket 或 raw metadata。手动 scheduler dry-run 只获取 cleanup lock、生成 readonly report、释放 lock 并写入 `dry_run` history；它不会启动 scheduler loop，不会生成可执行 signed cleanup plan，也不能作为删除授权。它不删除任务、文件 metadata 记录、审计记录或 `object_key`，也不触发 PDF 解析、翻译或 Word 生成流程。当前物理删除只支持 `local_file` 和 `local_object`，`s3` 会返回 unsupported 结果而不会执行真实对象存储删除。

存储使用汇总接口只面向 Admin，只基于 `document_files` metadata 的 `size_bytes` 做容量估算和 quota readiness 展示。quota policy dry-run 同样只读，用于预演拟上传文件在 staged policy 下是否会 warning/block。quota ops summary 只读展示真实阻断 readiness、rollback 配置建议和最近 block/override audit replay。真实上传授权会在 `FILES_QUOTA_POLICY_ENABLED=true`、`FILES_QUOTA_POLICY_DRY_RUN=false`、kill switch 关闭、配置有效且 projected usage 达到 block 阈值时执行阻断；Admin 可通过显式 override reason 和确认短语放行。quota enforcement 不验证对象是否真实存在，不上传文件内容，不执行 mark-expired、delete-preview、delete-expired、provider 调用或转换流程。

## API 参考

### `POST /api/v1/files/upload-url`

- 用途：为 PDF 创建上传授权。
- 请求体：JSON。

| 字段 | 必填 | 说明 |
|---|---|---|
| `filename` | 是 | 原始文件名。 |
| `mime_type` | 否 | 默认 `application/pdf`。 |
| `size_bytes` | 是 | 文件大小。 |
| `file_type` | 否 | 当前默认 `source_pdf`。 |
| `checksum_sha256` | 否 | `sha256:<hex>`。 |
| `job_id` | 否 | 可选关联任务。 |
| `quota_override_reason` | 否 | Admin-only quota override 原因；仅在 ready policy 触发 block 时生效。 |
| `quota_override_confirmation` | 否 | Admin-only quota override 确认短语，必须为 `OVERRIDE FILE QUOTA POLICY`。 |

- 响应：`201 Created`，包含 `file_id`、`upload_url`、`method=PUT`、`headers`、`expires_at`、`object_key`、`max_bytes` 和 `file`。
- 所有存储 provider（包括 `s3`）的 `upload_url` 均指向后端 `PUT /api/v1/files/{file_id}/content`。调用方上传时须携带响应中的 `headers` 和 Bearer token。
- 授权仅登记 `pending_upload` 元数据；内容校验及对象写入成功后才更新为 `uploaded`，此时才能创建 document job。
- quota 行为：
  - 默认配置下 quota policy disabled 或 dry-run，不影响上传授权。
  - 当 policy 状态为 `ready` 且 projected usage 达到 block 阈值时，返回 `409 conflict`，不创建 `document_files`，写入 `file.quota_policy_block` audit event。
  - Admin 携带有效 `quota_override_reason` 和 `quota_override_confirmation` 时可放行，写入 `file.quota_policy_override` audit event，然后继续写入 `file.upload_authorize`。
  - Operator 携带 override 字段不会放行。
- 成功动作写入 `file.upload_authorize` audit event。

### `PUT /api/v1/files/{file_id}/content`

- 用途：通过后端代理上传 PDF 内容，由后端写入配置的本地存储或 S3。
- 请求体：PDF 二进制。
- 关键行为：
  - 请求体不能超过 `JOBS_UPLOAD_MAX_BYTES`。
  - 上传需要继续带 Bearer token，沿用文件所有者或同租户、同公司 Admin 的访问限制。
  - 后端校验 PDF 内容、页数、授权大小和可选 checksum，成功写入对象后回填 checksum、page_count 和 etag，并把文件状态更新为 `uploaded`，以供创建 document job。
  - 内容校验或 S3 写入失败时保持 `pending_upload`，不写入 `file.upload_content` 成功审计。
- 响应：`201 Created`，返回 `file`。
- 成功动作写入 `file.upload_content` audit event。

### `GET /api/v1/files/{file_id}`

- 用途：读取文件 metadata。
- 响应：`DocumentFileResponse`。

### `GET /api/v1/files/library/search`

- 用途：Admin-only 只读搜索 `document_files` 安全摘要。
- 认证：Bearer JWT，Admin only。
- 查询参数：

| 字段 | 说明 |
|---|---|
| `page` | 页码，默认 1。 |
| `page_size` | 每页数量，默认 50，最大 200。 |
| `sort` | `created_at_desc`、`created_at_asc`、`updated_at_desc`、`updated_at_asc`、`expires_at_desc`、`expires_at_asc`、`size_bytes_desc`、`size_bytes_asc`。 |
| `q` | 在安全字段中搜索 file id、job id、file type、storage provider、原始文件名、mime type、status、created_by。 |
| `file_type` | 精确筛选 file type。 |
| `status` | 精确筛选 metadata status。 |
| `storage_provider` | 精确筛选 storage provider。 |
| `job_id` | 精确筛选 job id。 |
| `created_by` | 精确筛选创建者。 |
| `expires_from` / `expires_to` | 按 `expires_at` 范围筛选；缺失 `expires_at` 的记录不会匹配日期范围。 |
| `created_from` / `created_to` | 按 `created_at` 范围筛选。 |

- 行为：
  - 不修改 `document_files` metadata。
  - 不标记 expired。
  - 不执行 delete-preview、delete-expired 或 S3 删除。
  - 不写 audit event。
  - 不返回 `object_key`、`bucket`、`checksum_sha256`、`etag`、`metadata`、本地路径、文件内容或签名 URL。
- 响应：`FileLibrarySearchResponse`。

关键字段：

| 字段 | 说明 |
|---|---|
| `generated_at` | 搜索生成时间。 |
| `total` | 当前筛选命中的 metadata 行数。 |
| `filters` | 后端实际生效的筛选摘要。 |
| `items[].file_id` | 文件 ID，可用于后续 selected-file dry-run 流程。 |
| `items[].expired` | `expires_at` 是否已过期。 |
| `items[].physical_delete_candidate` | metadata 层面是否看起来满足本地物理删除首层条件；真实结果仍必须通过 `/retention/delete-preview` 验证。 |

### `GET /api/v1/files/retention/plan`

- 用途：读取 `document_files` 保留期 dry-run 计划。
- 认证：Bearer JWT，Admin only。
- 行为：
  - 基于 `expires_at` 选择过期候选。
  - `deleted` 状态文件不会进入候选。
  - 不修改 metadata。
  - 不删除任何本地文件或对象存储对象。
- 响应：`FileRetentionPlanResponse`。

关键字段：

| 字段 | 说明 |
|---|---|
| `generated_at` | 计划生成时间。 |
| `retention_days` | 当前后端配置的保留天数。 |
| `deletion_supported` | 是否存在后端支持的本地物理删除入口。 |
| `action_mode` | `dry_run`。 |
| `totals` | `files_seen`、`candidate_files`、`candidate_local_files`、`candidate_objects` 等计数。 |
| `candidates` | 过期候选文件 metadata，包含 `file_id`、`job_id`、`file_type`、`storage_provider`、`object_key`、`size_bytes`、`status`、`expires_at` 和 `reason`。 |

### `POST /api/v1/files/retention/mark-expired`

- 用途：把当前过期候选中仍为 `uploaded` 的文件 metadata 标记为 `expired`。
- 认证：Bearer JWT，Admin only。
- 行为：
  - 不删除任何本地文件或对象存储对象。
  - 不删除任务、文件 metadata 记录或 `object_key`。
  - 不触发任务处理主流程。
  - 成功动作写入 `file.retention_mark_expired` audit event。
- 响应：`FileRetentionPlanResponse`，其中：
  - `action_mode=mark_expired`
  - `marked_file_ids` 为本次从 `uploaded` 标记为 `expired` 的文件 ID。

### `GET /api/v1/files/retention/policies`

- 用途：列出 Admin-only `document_files` 保留策略和各 file type 的当前有效策略。
- 认证：Bearer JWT，Admin only。
- 行为：
  - 不修改策略。
  - 不修改 `document_files.expires_at`。
  - 不执行 metadata 标记、物理删除、定时清理或 quota enforcement。
- 响应：`FileRetentionPolicyListResponse`。

关键字段：

| 字段 | 说明 |
|---|---|
| `fallback_retention_days` | 未命中 published policy 时使用的 `oss_file_retention_days`。 |
| `effective[]` | 每个 file type 当前解析得到的有效策略，包含 `source`、`retention_days`、`policy_id` 和 `reason`。 |
| `items[]` | 全部 policy 历史记录；禁用策略也保留。 |

### `GET /api/v1/files/storage/usage`

- 用途：读取 `document_files` storage usage 和 quota readiness 的只读汇总。
- 认证：Bearer JWT，Admin only。
- 行为：
  - 基于 `DocumentFileRecord.size_bytes` 估算文件占用。
  - 按 storage provider、file type、status 聚合文件数和 bytes。
  - 估算已 expired 且满足本地物理删除首层条件的可回收空间。
  - 返回 artifact storage readiness 上下文，例如 `artifact_storage`、`artifact_root_writable`、`artifact_disk_free_bytes`。
  - 不修改 `document_files` metadata。
  - 不标记 expired。
  - 不执行物理删除或 S3 删除。
  - 不阻断上传或执行 quota enforcement。
  - 默认不写 audit event。
- 响应：`FileStorageUsageResponse`。

关键字段：

| 字段 | 说明 |
|---|---|
| `generated_at` | 汇总生成时间。 |
| `artifact_storage` | 当前 artifact storage backend。 |
| `artifact_root_writable` | 当前 artifact 本地根是否可写；来自 health readiness 语义。 |
| `artifact_disk_free_bytes` | 当前 artifact 本地根所在磁盘剩余字节数；对象存储 provider 下仍只代表本地运行时根。 |
| `totals.files_seen` | 扫描到的 `document_files` metadata 行数。 |
| `totals.active_size_bytes` | 非 `deleted` metadata 的估算总 bytes。 |
| `totals.expired_size_bytes` | 已过 `expires_at` 且非 `deleted` metadata 的估算 bytes。 |
| `reclaim.estimated_reclaimable_size_bytes` | `status=expired`、已过期、provider 为 `local_file` 或 `local_object` 且有 `object_key` 的 metadata 估算 bytes。实际是否可删除仍需 `/retention/delete-preview` 验证。 |
| `reclaim.unsupported_storage_size_bytes` | 已过期且 `status=expired`，但 provider 暂不支持物理删除，例如 `s3`。 |
| `reclaim.blocked_missing_object_key_size_bytes` | 已过期且 `status=expired`，但本地 provider 缺少 `object_key`。 |
| `reclaim.blocked_not_expired_status_size_bytes` | 已过 `expires_at` 但状态仍不是 `expired`，通常需要先经过 mark-expired 或正常上传状态收口。 |
| `quota.status` | Advisory-only quota 状态；当前第一版未配置时为 `not_configured`，不影响上传。 |
| `by_storage_provider[]` | 按 provider 汇总。 |
| `by_file_type[]` | 按 file type 汇总。 |
| `by_status[]` | 按 metadata status 汇总。 |

分组字段：

| 字段 | 说明 |
|---|---|
| `key` | provider、file type 或 status 值。 |
| `file_count` | 分组内 metadata 行数。 |
| `size_bytes` | 分组内 `size_bytes` 总和。 |
| `expired_count` | 分组内已过 `expires_at` 且非 `deleted` 的行数。 |
| `expired_size_bytes` | 分组内已过 `expires_at` 且非 `deleted` 的估算 bytes。 |
| `estimated_reclaimable_count` | 分组内满足 metadata-estimated reclaim 条件的行数。 |
| `estimated_reclaimable_size_bytes` | 分组内满足 metadata-estimated reclaim 条件的估算 bytes。 |

### `POST /api/v1/files/quota-policy/dry-run`

- 用途：预演一个拟上传文件在 staged quota policy 下的 warning/block 结果。
- 认证：Bearer JWT，Admin only。
- 请求体：JSON。

| 字段 | 必填 | 说明 |
|---|---|---|
| `size_bytes` | 是 | 拟上传文件大小，必须大于等于 0。 |
| `file_type` | 否 | 默认 `source_pdf`；当前只作为 dry-run 上下文返回，不改变真实上传行为。 |
| `filename` | 否 | 可选展示上下文，不读取本地文件。 |

- 配置来源：
  - `FILES_QUOTA_POLICY_ENABLED`
  - `FILES_QUOTA_POLICY_DRY_RUN`
  - `FILES_QUOTA_BYTES`
  - `FILES_QUOTA_WARNING_THRESHOLD_RATIO`
  - `FILES_QUOTA_BLOCK_THRESHOLD_RATIO`
- 行为：
  - 基于当前非 `deleted` 的 `document_files.size_bytes` 计算 `current_used_size_bytes`。
  - 使用请求的 `size_bytes` 计算 projected usage。
  - 返回 `would_warn`、`would_block` 和 reasons。
  - 如果 `size_bytes` 超过现有 `JOBS_UPLOAD_MAX_BYTES`，`would_block=true` 并返回 `upload_size_exceeds_max_bytes`；这只是 dry-run 报告，真实上传仍走现有上传校验。
  - 不创建 `document_files`。
  - 不生成 upload URL。
  - 不写 audit event。
  - 不执行真实 quota enforcement；真实阻断只发生在 `/upload-url` 且 policy status 为 `ready` 时。
  - 不上传文件内容。
  - 不调用 S3、provider、告警服务、parser、翻译或 Word 生成流程。
- 响应：`FileQuotaPolicyDryRunResponse`。

关键字段：

| 字段 | 说明 |
|---|---|
| `policy.status` | `disabled`、`not_configured`、`invalid`、`dry_run` 或 `ready`。 |
| `policy.configured` | 是否配置了正数 quota bytes。 |
| `policy.upload_max_bytes` | 当前既有上传大小上限。 |
| `usage.current_used_size_bytes` | 当前非 deleted metadata bytes。 |
| `usage.projected_used_size_bytes` | 当前使用量加上拟上传大小。 |
| `would_warn` | projected usage 是否达到 warning 阈值。 |
| `would_block` | projected usage 是否达到 block 阈值，或拟上传大小是否超过既有上传上限。 |
| `reasons[]` | 触发原因，例如 `quota_policy_disabled`、`quota_not_configured`、`projected_usage_reaches_block_threshold`。 |
| `safety.upload_authorization_created` | 始终为 `false`。 |
| `safety.upload_blocking_executed` | 始终为 `false`。 |
| `safety.metadata_mutated` | 始终为 `false`。 |
| `safety.audit_events_written` | 始终为 `false`。 |

### `GET /api/v1/files/quota-policy/ops-summary`

- 用途：读取 Admin-only quota enforcement 运维摘要、rollback 选项和 audit replay。
- 认证：Bearer JWT，Admin only。
- 查询参数：

| 字段 | 说明 |
|---|---|
| `replay_limit` | 返回最近 quota enforcement 审计事件数量，默认 20，范围 1-100。 |

- 行为：
  - 读取当前 quota policy 配置、当前 metadata 使用量和 kill switch 状态。
  - `enforcement_ready=true` 仅表示当前配置允许真实上传阻断执行；它不代表本次读取执行了阻断。
  - `current_usage_would_block` 使用 proposed size 0 评估当前 metadata 使用量是否已经达到 block 条件。
  - `rollback_options[]` 只返回配置开关建议，不写配置、不重启服务、不改变运行时 settings。
  - `audit_replay[]` 只从已有 `file.quota_policy_block` / `file.quota_policy_override` audit events 中提取安全摘要。
  - 不创建 `document_files`。
  - 不生成 upload URL。
  - 不执行真实 quota enforcement。
  - 不写 audit event。
  - 不调用 provider、S3、清理、scheduler、parser、翻译或 Word 生成流程。
- 响应：`FileQuotaPolicyOpsSummaryResponse`。

关键字段：

| 字段 | 说明 |
|---|---|
| `policy` | 与 dry-run 相同的归一化 policy 配置摘要。 |
| `usage` | 当前非 `deleted` metadata bytes，`proposed_upload_size_bytes=0`。 |
| `enforcement_ready` | policy status 为 `ready` 且 `FILES_QUOTA_POLICY_KILL_SWITCH=false` 时为 `true`。 |
| `kill_switch_enabled` | 当前 `FILES_QUOTA_POLICY_KILL_SWITCH` 状态。 |
| `rollback_options[].env_var` | 建议调整的环境变量，例如 `FILES_QUOTA_POLICY_KILL_SWITCH`、`FILES_QUOTA_POLICY_DRY_RUN`、`FILES_QUOTA_POLICY_ENABLED`。 |
| `rollback_options[].target_value` | 建议的回滚目标值。 |
| `rollback_options[].currently_effective` | 当前配置是否已经等于该 rollback 建议效果。 |
| `audit_replay_total` | 当前命中的 quota block/override 审计事件总数。 |
| `audit_replay_truncated` | 是否因 `replay_limit` 截断。 |
| `audit_replay[].outcome` | 从 details 或 action 推断的 `blocked` / `overridden`。 |
| `audit_replay[].projected_used_size_bytes` | 审计 details 中的 projected usage，旧事件缺失时为 `null`。 |
| `audit_replay[].override_applied` | 审计 details 中的 override 是否实际应用。 |
| `safety.read_only` | 始终为 `true`。 |
| `safety.upload_authorization_created` | 始终为 `false`。 |
| `safety.upload_blocking_executed` | 始终为 `false`。 |
| `safety.metadata_mutated` | 始终为 `false`。 |
| `safety.audit_events_written` | 始终为 `false`。 |
| `safety.cleanup_executed` | 始终为 `false`。 |
| `safety.scheduler_loop_executed` | 始终为 `false`。 |
| `safety.conversion_workflow_executed` | 始终为 `false`。 |

### `POST /api/v1/files/retention/policies`

- 用途：创建 draft 保留策略。
- 认证：Bearer JWT，Admin only。
- 请求体：JSON。

| 字段 | 必填 | 说明 |
|---|---|---|
| `name` | 是 | 策略名称。 |
| `scope_type` | 是 | `global` 或 `file_type`。 |
| `file_type` | 条件必填 | `scope_type=file_type` 时必填，例如 `source_pdf`、`generated_word`。 |
| `retention_days` | 是 | 1 到 3650。 |
| `description` | 否 | 策略说明。 |

- 行为：
  - 只创建 `draft` policy。
  - 不影响新文件，直到 publish。
  - 不修改历史 `document_files.expires_at`。
  - 成功动作写入 `file.retention_policy_create` audit event。
- 响应：`201 Created`，返回 `FileRetentionPolicyResponse`。

### `GET /api/v1/files/retention/policies/{policy_id}`

- 用途：读取单个保留策略。
- 认证：Bearer JWT，Admin only。
- 响应：`FileRetentionPolicyResponse`，包含 `is_default`、`is_effective` 和 `matching_file_count`。

### `PATCH /api/v1/files/retention/policies/{policy_id}`

- 用途：更新 draft 保留策略。
- 认证：Bearer JWT，Admin only。
- 行为：
  - 仅 `draft` policy 可编辑。
  - `published` 和 `disabled` policy 会返回 conflict。
  - 不修改历史 `document_files.expires_at`。
  - 成功动作写入 `file.retention_policy_update` audit event。
- 响应：`FileRetentionPolicyResponse`。

### `POST /api/v1/files/retention/policies/{policy_id}/impact-preview`

- 用途：dry-run 预览某个 policy 对当前 `document_files` 的影响。
- 认证：Bearer JWT，Admin only。
- 请求体：JSON，当前 `mode` 固定为 `candidate_policy`。
- 行为：
  - 不修改 policy。
  - 不修改历史 `document_files.expires_at`。
  - 不标记 expired。
  - 不执行物理删除。
  - 默认不写 audit event。
- 响应：`FileRetentionPolicyImpactResponse`，包含匹配文件、当前 `expires_at`、投影 `projected_expires_at`、是否会过期和汇总计数。

### `POST /api/v1/files/retention/policies/{policy_id}/publish`

- 用途：发布 draft policy，使其影响后续新文件的 `expires_at` 计算。
- 认证：Bearer JWT，Admin only。
- 请求体：JSON。

| 字段 | 必填 | 说明 |
|---|---|---|
| `reason` | 是 | 发布原因，不能为空，用于 audit event。 |

- 行为：
  - 仅 `draft` policy 可发布。
  - 发布后该 policy 成为同 scope 默认策略。
  - 同 scope 旧 published policy 保留历史，但 `is_default=false`。
  - 不修改历史 `document_files.expires_at`。
  - 成功动作写入 `file.retention_policy_publish` audit event。
- 响应：`FileRetentionPolicyResponse`。

### `POST /api/v1/files/retention/policies/{policy_id}/set-default`

- 用途：把已发布 policy 设为同 scope 默认策略。
- 认证：Bearer JWT，Admin only。
- 请求体：JSON，字段同 publish：`reason` 必填。
- 行为：
  - 仅 `published` policy 可设为默认。
  - 不修改历史 `document_files.expires_at`。
  - 成功动作写入 `file.retention_policy_set_default` audit event。
- 响应：`FileRetentionPolicyResponse`。

### `POST /api/v1/files/retention/policies/{policy_id}/disable`

- 用途：禁用 draft 或 published policy。
- 认证：Bearer JWT，Admin only。
- 请求体：JSON，字段同 publish：`reason` 必填。
- 行为：
  - 不删除 policy 历史记录。
  - 不修改历史 `document_files.expires_at`。
  - 成功动作写入 `file.retention_policy_disable` audit event。
- 响应：`FileRetentionPolicyResponse`。

### `POST /api/v1/files/retention/delete-preview`

- 用途：对人工选中的 `document_files` 执行物理删除 dry-run。
- 认证：Bearer JWT，Admin only。
- 请求体：JSON。

| 字段 | 必填 | 说明 |
|---|---|---|
| `file_ids` | 是 | 非空文件 ID 列表，单次最多 50 个，不能重复。 |

- 行为：
  - 不修改 metadata。
  - 不删除本地文件或对象存储对象。
  - 不写入 `file.retention_physical_delete` audit event。
  - 仅 `status=expired` 且 `expires_at <= now` 的 `local_file` 或 `local_object` 会返回 `deletable`。
  - `uploaded`、未过期、已删除、缺失、无 `object_key` 或 `s3` provider 均返回对应 skip/unsupported outcome。
  - `s3` provider 会返回 `s3_delete_contract` fake adapter evidence，包含 exact bucket/key/version 目标摘要和 `real_s3_delete_executed=false`。
- 响应：`FileRetentionDeleteResponse`，其中 `action_mode=delete_preview`，并返回每个文件的 outcome、reason、provider、object_key、size_bytes 和是否将修改 metadata。

### `POST /api/v1/files/retention/delete-expired`

- 用途：对人工选中且已 dry-run 核对的过期本地文件执行物理删除。
- 认证：Bearer JWT，Admin only。
- 请求体：JSON。

| 字段 | 必填 | 说明 |
|---|---|---|
| `file_ids` | 是 | 非空文件 ID 列表，单次最多 50 个，不能重复。 |
| `reason` | 是 | 操作原因，不能为空，用于 audit event。 |
| `confirmation` | 是 | 必须精确等于 `DELETE EXPIRED FILES`。 |

- 行为：
  - 只会删除 `status=expired`、`expires_at <= now`、provider 为 `local_file` 或 `local_object` 且路径位于受管存储目录下的对象。
  - 成功删除或本地对象已不存在时，将对应 metadata `status` 更新为 `deleted`，但保留 metadata row、`object_key`、任务、事件和审计记录。
  - `s3` provider 当前返回 `skipped_unsupported_storage`，并携带 `s3_delete_contract` fake adapter evidence；不会执行真实 S3 删除，也不会把 S3 metadata 标记为 `deleted`。
  - 非 `expired`、未过期、无 `object_key`、未知文件或路径越界会返回 skip/error outcome，不会删除对象。
  - 成功动作写入 `file.retention_physical_delete` audit event，reason 会包含人工原因和汇总计数。
- 响应：`FileRetentionDeleteResponse`，其中 `action_mode=delete_execute`。

`items[].s3_delete_contract` 仅在 `storage_provider=s3` 时返回，当前版本为 fake contract：

| 字段 | 说明 |
|---|---|
| `contract_version` | 当前为 `s3-delete-fake-v1`。 |
| `adapter_mode` | 当前固定为 `fake`，不代表真实 provider adapter 已启用。 |
| `bucket` / `object_key` / `version_id` | 来自 `document_files` metadata 的目标摘要；`version_id` 只读取 `metadata.s3_version_id`，缺失时为 `null`。 |
| `target_exact` | bucket 和 object_key 均非空时为 `true`。 |
| `missing_target_fields[]` | exact target 缺失字段。 |
| `expected_outcome` | 当前固定为 `fake_skipped`。 |
| `safety.real_s3_delete_executed` | 始终为 `false`。 |
| `safety.fake_s3_delete_executed` | 表示 fake adapter contract 已生成。 |
| `safety.metadata_mutated` | S3 skip item 始终为 `false`。 |
| `safety.requires_future_real_adapter` | 始终为 `true`，真实删除需未来单独任务批准。 |

### `POST /api/v1/files/retention/cleanup-runs/preview`

- 用途：对精确 `file_ids` 生成 cleanup run preview 和 `preview_hash`。
- 认证：Bearer JWT，Admin only。
- 请求体：JSON。

| 字段 | 必填 | 说明 |
|---|---|---|
| `file_ids` | 是 | 非空文件 ID 列表，复用物理删除 file ID 校验，单次最多 50 个，不能重复。 |
| `max_files` | 否 | 本次 cleanup run 的额外限流边界，1 到 50，默认 50。 |

- 行为：
  - 内部调用现有 `/retention/delete-preview` 同等 physical-delete preview 逻辑。
  - 不修改 metadata。
  - 不删除本地文件或对象存储对象。
  - 不写 audit event。
  - 不运行 scheduler loop。
- 响应：`FileRetentionCleanupRunResponse`，其中：
  - `run_id=cleanup_run_...`，并同步创建 durable history 记录
  - `action_mode=cleanup_preview`
  - `preview_hash=sha256:...`
  - `cleanup_plan.plan_id=cleanup_plan_...`
  - `cleanup_plan.signature_algorithm=hmac-sha256`
  - `cleanup_plan.expires_at` 为短期执行窗口，到期后必须重新 preview
  - `confirmation_phrase=EXECUTE AUTOMATED RETENTION CLEANUP`
  - `physical_delete.action_mode=delete_preview`
  - `safety.physical_delete_executed=false`
  - `safety.history_recorded=true`
  - `safety.signed_plan_created=true`
  - `safety.scheduler_loop_executed=false`

### `POST /api/v1/files/retention/cleanup-runs/execute`

- 用途：执行已 preview 的精确 cleanup run。
- 认证：Bearer JWT，Admin only。
- 请求体：JSON。

| 字段 | 必填 | 说明 |
|---|---|---|
| `file_ids` | 是 | 必须与 preview 时确认的精确文件 ID 列表一致。 |
| `max_files` | 否 | 本次 cleanup run 的限流边界，默认 50。 |
| `run_id` | 否 | preview 返回的 durable run ID；携带 signed plan 时必填。传入不存在的 `run_id` 会记录 failed history 并返回 conflict。 |
| `preview_hash` | 是 | 最近一次 cleanup preview 返回的 hash；执行前会重新 preview 并核对。 |
| `plan_id` | 否 | preview 返回的 `cleanup_plan.plan_id`；推荐传入。 |
| `plan_signature` | 否 | preview 返回的 `cleanup_plan.signature`；推荐传入。 |
| `reason` | 是 | 执行原因，不能为空，用于 audit event。 |
| `confirmation` | 是 | 必须精确等于 `EXECUTE AUTOMATED RETENTION CLEANUP`。 |

- 行为：
  - 重新执行 physical-delete preview 并核对 `preview_hash`。
  - 传入 preview `run_id` 时，成功执行会更新同一条 durable history 为 `executed`。
  - 传入未知 `run_id` 时，不执行物理删除、不写成功审计，记录 `failed` history 后返回 conflict。
  - 传入 `plan_id` 或 `plan_signature` 时，二者必须同时提供，且必须绑定同一 `run_id`。
  - signed plan 校验会在 physical-delete execution 之前完成；plan id、signature、file_ids、max_files、preview_hash 或过期时间不匹配时，不执行物理删除并记录 failed history。
  - 未传 `plan_id` / `plan_signature` 的旧客户端仍可按现有 `run_id + preview_hash` 合同执行；响应仍会返回 history 中保存的 `cleanup_plan`。
  - hash 不匹配时返回 conflict，要求重新 preview。
  - hash 匹配后调用现有 physical-delete execution primitive。
  - 仍只支持已 expired 的 `local_file` / `local_object`。
  - `s3` 仍返回 `skipped_unsupported_storage`，并通过 `physical_delete.items[].s3_delete_contract` 返回 fake adapter evidence；不会执行真实 S3 删除。
  - 成功动作写入 `file.retention_automated_cleanup_execute` audit event。
  - 不运行 scheduler loop、provider cancellation、alert delivery、pdf-mineru 解析、翻译或 Word 生成。
- 响应：`FileRetentionCleanupRunResponse`，其中：
  - `action_mode=cleanup_execute`
  - `physical_delete.action_mode=delete_execute`
  - `safety.physical_delete_executed=true`
  - `safety.physical_delete_contract_reused=true`
  - `safety.history_recorded=true`
  - `safety.signed_plan_created=true`
  - `safety.signed_plan_verified=true`，仅当 execute 请求携带并通过 plan 校验时为 true
  - `safety.s3_delete_executed=false`

重复对已删除目标执行时会复用 existing physical-delete 幂等语义，返回 `skipped_already_deleted` 或相关 skip outcome，而不是再次删除对象。

### `POST /api/v1/files/retention/cleanup-runs/scheduler-dry-run`

- 用途：手动运行一次 scheduler dry-run，生成 readonly cleanup report、cleanup lock evidence 和 durable history。
- 认证：Bearer JWT，Admin only。
- 请求体：JSON。

| 字段 | 必填 | 说明 |
|---|---|---|
| `owner_id` | 否 | cleanup lock owner。缺省为当前 admin 的 `manual:{user.id}`。 |
| `lock_ttl_seconds` | 否 | cleanup lock TTL，1 到 900 秒，默认 60 秒。 |

- 行为：
  - 先尝试 acquire `file_retention_cleanup` lock。
  - 已存在未过期 active lock 时返回 `409 conflict`，不生成 report，不写 history。
  - lock 成功后调用 readonly cleanup runner，组合 retention plan 和 storage usage。
  - 返回前释放本次 lock，并把 released evidence 写入 history。
  - 写入 `status=dry_run`、`action_mode=scheduler_dry_run` 的 durable history。
  - history 中保存 `readonly_report`、`lock`、`preview_hash`、candidate `file_id` 列表、totals 和 safety flags。
  - 不生成 signed cleanup plan；该报告不能作为 cleanup execute 或物理删除授权。
  - 不修改 `document_files` metadata。
  - 不执行 mark-expired、delete-preview、delete-expired、真实 S3 删除、provider cancellation、alert delivery 或 scheduler loop。
  - 不写 audit event。
  - 不触发 pdf-mineru 解析、翻译或 Word 生成。
- 响应：`FileRetentionCleanupSchedulerDryRunResponse`，其中：
  - `action_mode=scheduler_dry_run`
  - `readonly_report.mode=readonly_plan`
  - `lock.status=released`
  - `lock.released=true`
  - `safety.scheduler_loop_executed=false`
  - `safety.scheduler_manual_dry_run_executed=true`
  - `safety.metadata_mutated=false`
  - `safety.objects_deleted=false`
  - `safety.physical_delete_executed=false`
  - `safety.provider_calls_executed=false`
  - `safety.s3_delete_executed=false`
  - `safety.cleanup_lock_acquired=true`
  - `safety.cleanup_lock_released=true`

### `GET /api/v1/files/retention/cleanup-runs/history`

- 用途：分页列出 cleanup run durable history。
- 认证：Bearer JWT，Admin only。
- 查询参数：

| 字段 | 说明 |
|---|---|
| `page` | 页码，默认 1。 |
| `page_size` | 每页数量，默认 50，最大 100。 |

- 行为：
  - 只读查询，不执行 cleanup run。
  - 不启动 scheduler loop。
  - 不调用 provider cancellation、alert delivery、S3 delete 或主转换流程。
  - 不写 audit event。
  - 不返回本地路径、文件内容、bucket、`object_key` 或 raw metadata。
- 响应：`FileRetentionCleanupRunHistoryListResponse`，按 `updated_at` 倒序返回。

关键字段：

| 字段 | 说明 |
|---|---|
| `items[].run_id` | cleanup run ID。 |
| `items[].status` | `previewed`、`executed`、`failed` 或 `dry_run`。 |
| `items[].action_mode` | `cleanup_preview`、`cleanup_execute` 或 `scheduler_dry_run`。 |
| `items[].preview_hash` | preview safety hash。 |
| `items[].cleanup_plan` | signed cleanup plan 摘要，包含 plan id、过期时间、签名算法和签名；不包含 secret。 |
| `items[].readonly_report` | scheduler dry-run 的 readonly report；preview/execute history 通常为空。 |
| `items[].lock` | scheduler dry-run 的 cleanup lock evidence；preview/execute history 通常为空。 |
| `items[].requested_file_ids` | 本次请求的文件 ID 列表；不包含对象路径。 |
| `items[].totals` | physical-delete preview/execute 汇总计数。 |
| `items[].safety` | 本次 history 记录保存的 safety flags。 |
| `items[].reason` | execute 人工原因；preview 通常为空。 |
| `items[].error_code` / `items[].error_message` | execute 前置校验失败时的失败摘要。 |

### `GET /api/v1/files/retention/cleanup-runs/history/{run_id}`

- 用途：读取单条 cleanup run durable history。
- 认证：Bearer JWT，Admin only。
- 行为：
  - 只读查询，不执行清理动作。
  - 未找到时返回 `404 not_found`。
  - 响应不包含本地路径、文件内容、bucket、`object_key` 或 raw metadata。
- 响应：`FileRetentionCleanupRunHistoryResponse`。

常见 outcome：

| outcome | 说明 |
|---|---|
| `deletable` | 预览模式下符合物理删除条件。 |
| `deleted` | 执行模式下本地对象已删除，metadata 已标记为 `deleted`。 |
| `already_missing` | 执行模式下本地对象已不存在，metadata 已标记为 `deleted`，用于幂等收口。 |
| `skipped_not_expired_status` | metadata 状态不是 `expired`。 |
| `skipped_not_expired_time` | `expires_at` 仍晚于当前时间。 |
| `skipped_unsupported_storage` | provider 当前不支持物理删除，例如 `s3`。 |
| `skipped_missing_object_key` | 本地 provider 文件缺少 `object_key`。 |
| `failed` | 路径解析、metadata 更新或本地删除失败。 |

## 与 document_jobs 的关系

`POST /api/v1/document-jobs` 的 `source_file_id` 必须来自已成功上传的 `source_pdf` 文件。调用方不应绕过 Files API 直接构造 object key。
