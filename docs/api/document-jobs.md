---
doc_type: lib-api-ref
entry: document-jobs
category: endpoint
status: current
source_files:
  - app/api/v1/router.py
  - app/domains/document_jobs/router.py
  - app/domains/document_jobs/schemas.py
  - app/domains/document_jobs/models.py
  - app/domains/document_jobs/service.py
  - app/domains/document_jobs/execution.py
summary: Document Jobs API 提供 P0 PDF -> Word 任务创建、查询、事件、重试、clone、取消、归档、删除和下载入口。
tags: [document-jobs, api, pdf, word]
last_reviewed: 2026-10-16
---

## 概述

Document Jobs API 挂在 `/api/v1/document-jobs` 下，是当前 P0 PDF -> Word 工作台和 Golden Sample 回归使用的主链路。

典型流程：

```text
POST /api/v1/files/upload-url
PUT /api/v1/files/{file_id}/content
POST /api/v1/document-jobs
GET /api/v1/document-jobs/{job_id}
GET /api/v1/document-jobs/{job_id}/events
GET /api/v1/document-jobs/{job_id}/translation-batches
GET /api/v1/document-jobs/{job_id}/translation-qa
PATCH /api/v1/document-jobs/{job_id}/translation-qa
GET /api/v1/document-jobs/config-summary
POST /api/v1/document-jobs/bulk-retry
POST /api/v1/document-jobs/{job_id}/clone
POST /api/v1/document-jobs/bulk-archive
POST /api/v1/document-jobs/bulk-cancel
POST /api/v1/document-jobs/{job_id}/unarchive
POST /api/v1/document-jobs/{job_id}/delete-preview
POST /api/v1/document-jobs/{job_id}/delete
GET /api/v1/document-jobs/{job_id}/download-url
GET /api/v1/document-jobs/{job_id}/download?token=...
```

## 错误响应

Document Jobs API 使用统一错误结构，同时保留 FastAPI 兼容的 `detail` 字段：

```json
{
  "detail": "错误说明",
  "error_code": "conflict",
  "error": {
    "code": "conflict",
    "message": "错误说明",
    "status_code": 409,
    "trace_id": "trace_123"
  }
}
```

前端应优先读取 `error.code` / `error.message` / `error.trace_id`，兼容旧调用方时可继续读取 `detail` 和顶层 `error_code`。

CON-104 对已明确分类的下载拒绝 additive 返回 `error.reason_code`，例如 `job_deleted`、`job_not_completed`、`result_file_missing`、`result_file_mismatch`、`result_file_not_uploaded`、`file_expired`、`file_not_current`。保留原 HTTP 状态、`error.code`、`error_code` 和 `detail`；未提供细分码的其他错误不新增空 reason_code。权限检查优先按原 403/404 拒绝，不通过细分原因泄漏不可见任务或文件。

## 枚举

### `mode`

| 值 | 含义 |
|---|---|
| `direct_pdf_to_word` | 原文 PDF 转可编辑 Word；保持原文语言和语义，不调用 AI。 |
| `en2zh_pdf_to_word` | 英译中；先翻译 DocumentIR 再生成 Word。 |
| `ru2zh_pdf_to_word` | 俄译中；先翻译 DocumentIR 再生成 Word。 |
| `zh2en_pdf_to_word` | 中译英；先翻译 DocumentIR 再生成 Word。 |
| `zh2ru_pdf_to_word` | 中译俄；先翻译 DocumentIR 再生成 Word。 |

### `stage` 与执行边界（CON-102 候选）

CON-102路径A候选采用first-valid-receipt控制自动恢复；实际验证与独立复核见当前Trellis任务的receipt-validation.md和receipt-review.md。生产写者启用仍要求真实MySQL并发及部署文件系统锁语义专项通过，本轮未部署。

`status` 继续表示 `pending/queued/running/succeeded/failed/canceled`；`stage` 表示正在处理的工作，不能用于推断质量结论、复核或发布资格。

```text
direct：uploaded → parsing → parsed → ir_converting
        → rendering → quality_checking → uploading → completed
翻译： uploaded → parsing → parsed → ir_converting → translating
        → translation_validating → rendering → quality_checking → uploading → completed
```

- `translating`：创建和执行翻译批次，保持现有重试、拆批与调用预算；单批次的状态不等于主任务阶段。
- `translation_validating`：当前 generation 有效叶子批次全部成功（或没有可翻译单元）后，执行现有 ID 合并校验和回填。该阶段不代表已新增技术 Token、数字或术语检查算法。
- `quality_checking`：执行现有 DOCX evidence 和确定性内容完整性门禁。检查通过后才登记用户主 DOCX；完整性失败仍使用 `render_failed`，不会生成可下载的伪成功主件。
- 原文转换跳过两个翻译阶段，不加载 Provider、翻译 Prompt 或翻译术语。

三个新阶段均属于 `status=running`，支持取消、超时定位和恢复。失败终态仍为 `status=failed, stage=failed`，由 `failed_stage` 保存真正失败的位置。事件 `stage` 与实际工作一致，携带 generation、trace 和安全摘要；`duration_ms` 是本次可测调用的耗时，未知全阶段耗时保持空值。

旧阶段和历史记录保留。响应中的 `stage`/`failed_stage` 继续使用字符串，前端对未知阶段显示原值；事件和异常筛选只接受服务端支持的阶段。`available_actions` 仍是动作可用性的权威来源。CON-103 增加下述独立状态字段，当前没有批准发布或发布动作。

恢复保留最终IR和资源快照，不重复已完成的解析或翻译。`quality_checking` 或尚未选定结果的 `uploading` 在现有replay触发时，可条件回到 `rendering` 重建丢失的字节并重新检查；恢复事件记录来源阶段，进度不下降。质量通过后，每次尝试先登记内部pending候选，再写独立对象路径；仓储原子选定第一份有效结果凭据，所有恢复者只登记其同一个文件并完成任务。已有凭据时不再重渲染、换件或重写对象。此机制不增加持续扫描器、租约或公开状态字段。

候选不是用户主件。任务文件列表、按文件ID签发和技术Token消费均只允许合法完成任务的当前结果指针；pending、落选或取消后未绑定的候选不能下载。既有租户/公司/owner、Token签名/过期和文件有效期校验保持。自动发现legacy主件必须是唯一可核验的当前generation/最终IR文件；无generation、旧代、不同IR或矛盾多件不自动晋升。明确绑定的 `result_file_id` 按既有重试语义验证和复用，历史文件/审计保留。

部署时先升级能读取并保留新阶段/内部结果凭据、具备局部原子写入和候选可见性的兼容版本；全部旧API写者和Worker退出后才启用新写者。回滚先停止消费/投递和相关写入，由支持凭据的新执行器收敛或保留在途，再回兼容版本；兼容读者保留HEAD旧执行器时，所有DocumentJob消费/内联执行均维持暂停，不仅暂停新阶段/凭据任务；该候选不作为活跃Worker回退版本。仅扩stage的旧兼容补丁不足以安全回退，不能删除字段、文件或审计伪装兼容。

### 质量、复核和交付状态（CON-103）

全部 DocumentJob 响应（含列表、详情、创建、retry/clone 和 incidents 内的任务）增加以下只读字段。请求不能任意指定这些状态；现有 `status` 仍表示执行状态。

| 字段 | 取值 | 默认值 |
|---|---|---|
| `quality_status` | `pending / passed / warning / blocked` | `pending` |
| `review_status` | `unreviewed / approved / needs_fix / blocked` | `unreviewed` |
| `delivery_status` | `internal_draft / ready_to_publish / published` | `internal_draft` |
| `quality_summary` | JSON 对象 | `{}` |

`pending` 和空摘要表示尚无任务级质量证据，不增加 `unavailable` 枚举。成功执行、已有 DOCX、direct 模式、旧 QA 结论或 Golden signoff 都不会自动提升状态；当前也不将 renderer metadata 自动聚合为质量通过。现有业务路径只产生 `internal_draft`，尚未提供 ready/published 的写入口。

质量为 `blocked` 或复核为 `unreviewed` 的合法成功主件仍可内部下载，继续校验任务归属、当前结果、文件有效期与 Token。该下载不授予批准或发布资格；前端继续消费后端 `available_actions`。后续交付晋升至少要求质量为 `passed/warning`、复核为 `approved`、执行成功并存在当前结果，预览和有效 Admin 发布证据由后续交付流程校验。

retry 的新 generation、clone 以及已有主件真正替换均使旧状态证据失效。首次绑定结果不会清除本代已有质量 blocker。已发布投影不得通过先降为草稿再原地换件或换代来绕过不可变保护；归档等非内容元数据仍沿用现有规则。

### 失败诊断字段

失败任务会在详情中返回：

- `failed_stage`
- `error_code`
- `error_message`

前端和联调脚本应优先用这三个字段定位上传、解析、IR、翻译、翻译合并校验、渲染、质量检查或对象存储问题。

### `translation_qa_status`

| 值 | 含义 |
|---|---|
| `unreviewed` | 未复核。 |
| `approved` | 已通过。 |
| `needs_fix` | 需要修正或跟进。 |
| `blocked` | 阻塞或无法判断。 |

该字段是 `review_status` 的兼容投影。历史未绑定当前结果/hash/generation 的 QA 原值保留在存储中，但不会自动成为新模型的有效批准；新模型为 `unreviewed` 时，响应中的旧 issue/note/reviewer/time 为空，原始存储不被清除。direct 不再自动推导 `approved`，旧翻译 QA 仍不可用。

列表筛选传 `translation_qa_status` 时，后端只返回翻译模式且当前复核状态匹配的任务；行响应、筛选和 `translation_qa_summary` 使用同一状态来源。

## API 参考

### `POST /api/v1/document-jobs`

- 用途：用已上传 PDF 创建转换任务。
- 请求体：JSON。

| 字段 | 必填 | 说明 |
|---|---|---|
| `source_file_id` | 是 | 来自 Files API 的 source PDF file id。 |
| `mode` | 否 | 默认 `direct_pdf_to_word`；翻译模式还包括 `en2zh_pdf_to_word` / `ru2zh_pdf_to_word` / `zh2en_pdf_to_word` / `zh2ru_pdf_to_word`，新调用优先传 `translation_mode`。 |
| `translation_mode` | 否 | `direct` / `en2zh` / `ru2zh` / `zh2en` / `zh2ru`。 |
| `document_language` | 否 | `auto` / `zh` / `en` / `ru`，默认 `auto`。 |
| `template_version_id` | 否 | 模板版本选择；创建任务时普通用户和 Admin 都可以绑定 published 版本。 |
| `term_version_id` | 否 | 旧翻译术语版本字段，仅跨语言任务可显式指定。 |
| `term_rule_set_id` | 否 | 符号与排版规则集，原文转换和翻译任务均可使用。 |
| `term_rule_set_version` | 否 | 符号与排版规则集版本。 |
| `translation_term_set_id` | 否 | 仅跨语言任务使用的翻译术语集。 |
| `translation_term_version` | 否 | 仅跨语言任务使用的翻译术语集版本。 |
| `translation_profile_id` | 否 | 仅跨语言任务使用的翻译配置 ID，可显式选择 published 版本。 |
| `translation_profile_version` | 否 | 仅跨语言任务使用的翻译配置版本。 |
| `debug_full_text` | 否 | 是否保留全文调试信息。仅翻译任务支持，且只有 admin 可以开启；默认关闭。 |

- 响应：`201 Created`，包含 `job_id`、`status`、`stage`、`progress` 和完整 `job`。
- 成功动作写入 `document_job.create` audit event。
- Readiness gate：当 `p0_document_jobs_required=true` 且 `p0_document_jobs_ready=false` 时，返回 `503 document_jobs_not_ready`，不会创建 job，也不会把 source file 绑定到 job。
- 权限：已登录创建用户可以在创建任务时绑定 published 资源版本；配置维护、发布、设默认仍走各资源管理接口权限。`debug_full_text` 只有 admin 可以开启。

原文转换请求示例：

```json
{
  "source_file_id": "file_uploaded_pdf",
  "translation_mode": "direct",
  "document_language": "auto"
}
```

原文转换不加载翻译术语、Translation Profile、翻译 Prompt 或 AI Provider；模板与符号规则仍可绑定。服务端保留历史输入归一化，新调用只使用表中的规范值，响应与新任务快照只记录规范模式。

- 规范化后 `mode` 与 `translation_mode` 不一致：`400 invalid_request`。
- 未知模式、空串或字段类型错误：`422 validation_error`。
- direct 显式指定任一非空翻译资源字段（包括旧 `term_version_id`）：`400 invalid_request`，拒绝发生在资源加载、任务创建、源文件绑定和队列投递前。
- direct 请求 `debug_full_text=true`：Operator 保持 `403 role_forbidden`；Admin 返回 `400 invalid_request`。

该 direct 约束针对新写入意图；历史任务的惰性资源字段仍可读取，不清理历史快照或审计。

### `GET /api/v1/document-jobs/config-summary`

- 用途：读取创建/重试任务所需的配置摘要。
- 认证：Bearer JWT；兼容 legacy `X-Admin-Token`，用于 P1/P2 只读预检脚本在没有内部账号密码时读取 runtime readiness。
- 响应：
  - `role`
  - `resource_mode`：`legacy` / `versioned`
  - `defaults`：默认 Template、Term Rule Set、legacy `en2zh` Translation Term Set、legacy `en2zh` Translation Profile 摘要
  - `translation_defaults`：按 `language_pair` 返回 `en2zh` / `ru2zh` / `zh2en` / `zh2ru` 的默认 Translation Term Set 与 Translation Profile
  - `options`：创建任务可绑定的 published 版本
  - `readiness`：创建任务前的只读配置状态
    - `en2zh_available`：默认翻译术语集和翻译配置是否可用。
    - `ru2zh_available`：默认俄译中翻译术语集和翻译配置是否可用。
    - `translation_modes`：按四种 `language_pair` 返回可用状态；`zh2en` / `zh2ru` 缺失时应视为不可用，不得复用旧专用布尔字段。
    - `p0_document_jobs_required`：当前环境是否要求 P0 document_jobs 自动执行链路通过门禁。
    - `p0_document_jobs_ready`：P0 document_jobs 自动执行链路是否通过门禁。
    - `document_jobs_worker_backend`：`disabled` / `celery` / `eager`。
    - `document_jobs_automatic_execution_enabled`：当前 worker backend 是否会自动执行任务。
    - `blockers`：P0 门禁阻断项，上传页应在 required 且 not ready 时阻止创建任务。
    - `warnings`：非阻塞 warning。
- 语义：只读聚合接口，不修改默认指针、不导入导出术语、不触发任务处理。
- 该摘要包含所有模式的资源元数据；direct 页面只展示模板与符号规则，隐藏翻译资源配置细节。翻译资源缺失不阻止 direct 创建，但 P0 执行 blockers 和其他配置错误仍有效。

### `GET /api/v1/document-jobs`

- 用途：分页查询任务列表。
- 查询参数：

| 参数 | 默认值 | 说明 |
|---|---|---|
| `page` | `1` | 从 `1` 开始。 |
| `page_size` | `20` | 当前限制 `1-100`。 |
| `status` | 无 | 按任务状态过滤。 |
| `status_group` | 无 | 状态组过滤；OpenAPI 枚举当前仅允许 `active`，等价于 `pending` / `queued` / `running`。不能与 `status` 同时使用。 |
| `translation_qa_status` | 无 | 按翻译 QA 状态过滤；OpenAPI 枚举允许 `unreviewed` / `approved` / `needs_fix` / `blocked` / `all`，传 `all` 时返回全部翻译模式 QA 任务。 |
| `q` | 无 | 按任务 ID、源文件 ID、源文件名、错误码或错误信息搜索。 |
| `sort` | `created_at_desc` | `created_at_desc` / `created_at_asc` / `updated_at_desc` / `updated_at_asc`。 |
| `include_archived` | `false` | 是否包含已归档任务；已删除任务始终不进入列表。 |
| `created_from` | 无 | 按创建时间下界过滤，ISO datetime。 |
| `created_to` | 无 | 按创建时间上界过滤，ISO datetime。 |

- 响应：`items`、分页信息、`summary`、`filtered_summary` 和 `translation_qa_summary`。
    - `summary`：当前用户可见任务在归档过滤后的全局状态计数，保留旧语义。
    - `filtered_summary`：应用 `status`/`status_group`、`translation_qa_status`、搜索、日期等筛选后的状态计数，不受分页影响。
    - `translation_qa_summary`：应用非 QA 状态筛选、搜索、日期和归档过滤后的 QA 状态计数，键为 `unreviewed`、`approved`、`needs_fix`、`blocked`。
    - 前端应兼容旧响应或局部 mock 未返回新增 summary 字段的情况，缺省按空对象处理。

### `GET /api/v1/document-jobs/{job_id}`

- 用途：读取任务详情。
- 响应：`DocumentJobResponse`，包括状态、阶段、进度、中间产物 file id、失败诊断字段、retry count、`source_job_id`、删除元数据 `deleted_at` / `deleted_by` / `delete_reason`、request snapshot 和 `available_actions`。
- 已删除任务仍可通过详情读取 metadata、事件和审计证据，但所有任务动作都会被禁用；默认列表不会返回已删除任务。
- `available_actions` 是服务端对当前用户和任务状态的操作可用性判断，键包括原有 `download`、`retry`、`cancel`、`archive`、`unarchive`、`clone`、`delete`，以及 additive 的 `publish`。旧客户端可忽略新键。每个 action 保留：

| 字段 | 说明 |
|---|---|
| `enabled` | 当前用户能否执行该动作。 |
| `disabled_reason` | 禁用原因；`enabled=true` 时为 `null`。 |
| `retryable` | 仅用于 `retry` 动作，表示失败是否属于可重试失败；其他动作固定为 `false`。 |

### 下载与发布资格（CON-104）

`download` 新增只读 `classification`、`warning_code`、`warning_message`。合法成功的当前主 DOCX 为 `classification=internal_only`，仅供内部检查；复核 approved 也不会自动生成最终交付分类。不能下载时分类为空，实际授权仍须核对文件和当次任务状态。

主要 warning 按以下顺序选择：质量 blocked → `quality_blocked_not_deliverable`；复核 blocked → `review_blocked_not_deliverable`；needs_fix → `review_needs_fix_not_deliverable`；unreviewed → `document_unreviewed_not_deliverable`；质量 pending → `quality_pending_not_deliverable`。warning code 与中文 message 配对；其余已批准且质量 passed/warning 的结果仍保留 internal_only 标签。完整质量证据继续独立展示。

`download` 与 `publish` 提供稳定 `disabled_reason_code`；`disabled_reason` 仍为可读文本。`publish` 另提供有序 `disabled_reasons=[{code,message}]`，首项与 singular 字段一致，以及核心资格 `eligible`：

| 当前条件（主件合法可用） | download | publish.eligible | publish.enabled |
|---|---|---|---|
| quality blocked | 内部下载，质量阻塞 warning | false | false |
| review unreviewed/needs_fix/blocked | 内部下载，对应 review warning | false | false |
| quality passed/warning + review approved + Admin | 内部下载 | true | false |
| 同一已批准任务的 Operator | 内部下载 | false，admin_required | false |
| quality pending，即便 review approved | 内部下载，质量未完成 warning | false | false |

`eligible` 只表示任务状态/当前用户/主件 metadata 的核心资格，不能当作可执行发布。CON-104 尚未接通发布所需预览验证和真实发布，`enabled` 始终 false，原因包含 `preview_unavailable`、`publication_unavailable`，并优先列出实际的核心拒绝。没有新增 publish endpoint、PublicationRecord 或交付状态写入。未来完整发布仍需验证绑定当前结果的批准、预览和不可变发布证据。

列表、详情、创建/retry/clone 和异常队列嵌套任务均由同一服务投影动作；前端不得以角色、status、quality/review 或旧 translation QA 重新计算资格。旧后端缺 publish 时保持禁用；下载新字段缺失时只能显示分类未知，不推断可交付。

### `GET /api/v1/document-jobs/{job_id}/events`

- 用途：读取任务事件。
- 响应：事件列表，包含 `stage`、`level`、`event_type`、`message`、`payload`、`duration_ms` 和 `trace_id`。

### `GET /api/v1/document-jobs/{job_id}/files`

- 用途：读取任务详情页可展示和可签发下载链接的文件摘要。
- 响应使用安全摘要：包含 `id`、`file_type`、`storage_provider`、`original_filename`、`mime_type`、`size_bytes`、`status`、`expires_at`、创建信息和 `quality_evidence`。
- 不返回 `bucket`、`object_key`、`checksum_sha256`、`etag`、raw `metadata`、本地路径、文件内容或签名 URL。
- `quality_evidence` 只对白名单质量字段开放，用于详情页和 Golden Sample 人工复核定位问题。

### `generated_word.metadata.docx_quality`

成功任务登记 `generated_word` 文件时，会在文件 metadata 中写入轻量 DOCX 结构证据；任务详情和下载签发响应只通过 `quality_evidence` 暴露白名单摘要。该字段是机器线索，不替代 admin 对最终 Word 排版质量的签字。

`generated_word.metadata.quality_flags` 会从 `docx_quality` 派生明确风险项，例如 `docx_quality_unavailable`、`docx_analysis_error`、`docx_no_editable_content`、`docx_image_only_suspected`、`docx_latex_residue:{count}`、`docx_manual_list_markers:{count}`、`docx_plain_toc_entries:{count}` 和 `docx_unstyled_heading_candidates:{count}`。`wide_table_count` 和 `landscape_sections` 仍作为结构证据暴露；portrait 源页上的宽表应保持 editable table 并适配 portrait 页面，不再因为没有 landscape section 而生成风险 flag。这些 flag 只用于让详情页进入“带自动标记的人工复核”状态，不会绕过或替代 admin manual sign-off。

常用字段：

| 字段 | 说明 |
|---|---|
| `editable_content_available` | 是否存在可编辑文本或 Word table 证据。 |
| `image_only_suspected` | 是否疑似只包含图片而缺少可编辑内容。 |
| `heading_paragraphs` | 通过 paragraph style 或 styles.xml 识别出的 Word heading 段落数。 |
| `heading_like_paragraphs` / `heading_like_unstyled_paragraphs` | 非表格正文段落中疑似标题的数量，以及其中未使用 Word heading 样式的数量。 |
| `numbering_paragraphs` | 使用 Word numbering 的段落数。 |
| `manual_list_marker_paragraphs` | 非表格正文段落中仍以字符 bullet/dash 呈现的列表项数量。 |
| `toc_tab_leader_paragraphs` | 带点线 leader 制表位的目录式段落数。 |
| `plain_toc_entry_paragraphs` | 疑似目录项但仍是普通点线/页码文本的段落数量。 |
| `table_count` / `table_shapes` | Word table 数量和行列形状。 |
| `wide_table_count` | 6 列及以上 Word table 数量，用于提示 datasheet 宽表版面风险。 |
| `table_header_rows` | 设置为重复表头的行数。 |
| `table_no_split_rows` | 设置防跨页断行的表格行数。 |
| `table_cell_zero_spacing_paragraphs` | 表格单元格内零段前后距段落数。 |
| `landscape_sections` | 横向 section 数量。 |
| `latex_residue_count` / `latex_residue_examples` | 可见文本中的疑似 LaTeX 残留计数和示例。 |

### `GET /api/v1/document-jobs/{job_id}/translation-batches`

- 用途：读取单个 document job 的 translation provider batch 只读诊断摘要，用于任务详情和运维排障。
- 响应：`DocumentJobTranslationBatchListResponse`，包含 `job_id`、当前 `generation` 和 batch `items`。
- 常用 batch 字段包括 `batch_id`、`status`、`page_start` / `page_end`、`item_count`、`char_count`、`attempt_count` / `max_attempts`、`split_level`、`parent_batch_id`、`root_batch_id`、`finish_reason`、`error_code`、`error_message`、`retryable`、`truncation_retry`、`result_file_id`、`ai_call_log_file_ids` 和 `updated_at`。
- 该接口只返回摘要和文件 ID，不返回完整 prompt、provider response、source text、translated text、debug archive 内容、对象存储定位或签名 URL。
- 该接口不提供批次级 retry、cancel、requeue 或 fan-in 写操作；任务级操作仍以 `available_actions` 和现有 document job action endpoint 为准。

### `GET /api/v1/document-jobs/{job_id}/translation-qa`

- 用途：读取翻译结果 QA 证据摘要和任务级复核状态。
- 支持范围：`en2zh_pdf_to_word` / `ru2zh_pdf_to_word` / `zh2en_pdf_to_word` / `zh2ru_pdf_to_word` 任务具备翻译 QA 证据；其他模式返回 `available=false` 和 `availability_reason=unsupported_mode`。
- 查询参数：

| 参数 | 默认值 | 说明 |
|---|---|---|
| `limit` | `200` | 返回最终文本片段数量，限制 `1-500`。 |

- 响应包含：
  - `qa`：任务级复核状态、问题归因、备注、复核人和复核时间。
  - `artifacts`：`document_ir`、`ai_call_log`、`ai_debug_archive` 文件 ID 摘要，以及 latest debug archive 的过期时间、是否过期、是否包含全文。
  - `summary`：最终片段数、返回片段数、quality flags、AI call 数、术语 trace 数、`debug_full_text_enabled` 和源文对照可用性。
  - `segments`：从 `document_ir` 读取的最终文本片段；只有 debug archive 存在且未过期时才带源文/AI 译文对照。
  - `term_traces`：从 `ai_call_log` 读取的脱敏术语命中摘要。
  - `ai_calls`：metadata-only AI 调用摘要，不包含完整 prompt、response、正文或密钥。
- 证据读取只消费已登记文件，不触发 PDF 解析、翻译 provider 调用或 Word 生成。

### `PATCH /api/v1/document-jobs/{job_id}/translation-qa`

- 用途：保存任务级翻译 QA 复核结论。
- 支持范围：四种翻译任务模式；其他模式返回 `409 conflict`。
- 请求体：

| 字段 | 必填 | 说明 |
|---|---|---|
| `status` | 是 | `unreviewed` / `approved` / `needs_fix` / `blocked`。 |
| `issue_type` | 否 | `translation` / `terminology` / `layout` / `source_quality` / `artifact_missing` / `other`。 |
| `note` | 否 | 备注，最多 1000 字符。 |

- 返回：`job_id`、最新 `qa` 和最新 `job`。
- 权限：沿用 Operator/Admin 的 tenant/company/owner 可见性；Operator 可为自己的翻译任务提交 QA 结论。`approved` 要求执行成功、当前可用主 DOCX、质量非 `blocked`；它不等于未来 Admin 发布批准，也不自动改变交付状态。
- 并发：服务校验后仍需在同任务锁/短事务内核对 generation、当前结果和最新质量。任务换代、换件或质量阻塞后，旧批准请求返回 `409 conflict`；不会放宽执行终态 CAS。
- 事件：成功保存会写入 `translation_qa_updated` 任务事件，`observed_review_status` 是服务锁外读取的状态，`review_status` 是本次 CAS 提交的结论；并发保存时前者不保证是锁内真实前驱。另记录 generation、结果标识/已有 checksum、trace、问题归因、复核人和备注长度，不写入全文正文、备注全文、prompt、response 或密钥。状态与事件沿用既有分步存储，不承诺跨仓储原子提交；事件存储错误不会被吞掉。

### `POST /api/v1/document-jobs/{job_id}/retry`

- 用途：对失败任务重试。
- 请求体可包含 `reason`、`use_latest_term_assets` 和术语资产选择字段。
- 成功动作写入 `document_job.retry` audit event。
- 权限：Operator 只能提交原因并沿用原配置；Admin 可选择使用最新默认术语资产或指定 published 术语资产。Retry 当前不重新绑定模板或翻译配置。
- 边界：Retry 只用于失败任务原地重试，不创建新任务，不等同于 clone。
- direct 只能重选符号与排版规则，显式选择翻译术语被拒绝；沿用历史快照时不重新加载惰性的翻译字段。

### `POST /api/v1/document-jobs/{job_id}/clone`

- 用途：基于已有任务源 PDF 创建一个新的 document job，语义是 “rerun as new job”。
- 行为：不会修改源任务，不增加源任务 `retry_count`，不会把源文件归属改到新任务；新任务的 `source_job_id` 指向源任务。
- 请求体：

| 字段 | 必填 | 说明 |
|---|---|---|
| `reason` | 否 | 操作原因。 |
| `config_strategy` | 否 | `keep_source_snapshot` / `use_current_defaults` / `select_published_versions`，默认 `keep_source_snapshot`。 |
| `document_language` | 否 | 覆盖新任务文档语言；未传则沿用源任务。 |
| `template_version_id` | 否 | 仅 `select_published_versions` 下可传，Admin-only。 |
| `term_rule_set_id` / `term_rule_set_version` | 否 | 仅 `select_published_versions` 下可传，Admin-only。 |
| `translation_term_set_id` / `translation_term_version` | 否 | 仅跨语言任务的 `select_published_versions` 下可传，Admin-only。 |
| `translation_profile_id` / `translation_profile_version` | 否 | 仅跨语言任务的 `select_published_versions` 下可传，Admin-only。 |
| `debug_full_text` | 否 | 覆盖新任务 debug 全文开关。 |

`debug_full_text=true` 只允许 admin 使用。Operator clone 已开启全文归档的源任务时，若使用 `keep_source_snapshot` 继承该开关，也会被拒绝；应由 admin 创建 P1 QA 样本任务或 clone 任务。

direct clone 不绑定翻译资源：新显式选择被拒绝；`keep_source_snapshot` 保留历史惰性字段以追溯，但不加载它们、不改源任务；`use_current_defaults` 只解析普通转换资源。任务详情隐藏 direct 的翻译资源和 AI 调试展示项，仅对展示快照做投影，不改变后端快照和权限。

- 成功：`201 Created`，返回 `source_job_id`、新 `job_id` 和完整新 `job`，并写入 `job_cloned` 任务事件和 `document_job.clone` audit event。
- 失败：源 PDF 不存在、不可见、过期或不是 uploaded source PDF 时返回 404/403/409；Operator 传显式资源版本返回 403。

### `POST /api/v1/document-jobs/bulk-retry`

- 用途：批量重试失败任务。
- 请求体：`job_ids` 加单任务 retry 的现有选项字段。
- 行为：逐个复用单任务 retry 语义，支持部分成功；不会因为某个任务失败而阻断后续任务。
- 成功项写入 `document_job.retry` audit event。
- 响应：`action=retry`、`total`、`succeeded`、`failed`、`items`。

单个 `items` 元素：

| 字段 | 说明 |
|---|---|
| `job_id` | 本次处理的任务 ID。 |
| `ok` | 单项是否成功。 |
| `status_code` | 成功为 `200`，失败为单任务接口对应 HTTP 状态。 |
| `error_code` | 失败时返回稳定错误码，成功为 `null`。 |
| `detail` | 失败原因，成功为 `null`。 |
| `job` | 成功时返回最新任务摘要，失败为 `null`。 |

### `POST /api/v1/document-jobs/{job_id}/cancel`

- 用途：取消可取消任务。
- 成功动作写入 `document_job.cancel` audit event。

### `POST /api/v1/document-jobs/bulk-cancel`

- 用途：批量取消 pending / queued / running 任务。
- 请求体：`job_ids`。
- 行为：逐个复用单任务 cancel 语义；取消只标记任务为 `canceled` 并停止后续处理，不承诺强制中断已进入外部服务的长任务。
- 成功项写入 `document_job.cancel` audit event。
- 响应结构同 `bulk-retry`，`action=cancel`。

### `DELETE /api/v1/document-jobs/{job_id}`

- 用途：归档任务。
- 成功动作写入 `document_job.archive` audit event。
- 边界：归档不是删除，不删除源文件、结果文件、debug/log 文件或事件。

### `POST /api/v1/document-jobs/{job_id}/unarchive`

- 用途：取消归档，让任务重新出现在默认列表中。
- 行为：清空 `archived_at` / `archived_by`，保留所有文件和事件；未归档任务调用该接口是幂等 no-op。
- 成功动作写入 `document_job.unarchive` audit event，并写入 `job_unarchived` 任务事件。

### `POST /api/v1/document-jobs/bulk-archive`

- 用途：批量归档 succeeded / failed / canceled 终态任务。
- 请求体：`job_ids`。
- 行为：逐个复用单任务 archive 语义；归档只从默认列表隐藏任务，不删除源文件、结果文件、debug/log 文件或事件。
- 成功项写入 `document_job.archive` audit event。
- 响应结构同 `bulk-retry`，`action=archive`。

### `POST /api/v1/document-jobs/{job_id}/delete-preview`

- 用途：Admin-only 预览删除任务会影响哪些文件。
- 行为：只读，不修改任务、文件、事件或审计。
- 限制：仅 `admin` 可调用，且仅 `succeeded` / `failed` / `canceled` 终态任务允许删除；`pending` / `queued` / `running` 返回 `409 conflict`。Operator 返回 `403 forbidden`，前端应隐藏任务级删除入口。
- `delivery_status=published` 的预览和执行均在任何文件副作用前返回 `409 conflict`，后端 delete 动作使用同一禁用原因；归档等非内容元数据仍按现有权限允许。
- 响应：
  - `confirmation_phrase`：兼容旧前端的确认短语，例如 `DELETE docjob_xxx`；当前 admin UI 不再要求输入该短语。
  - `preview_hash`：执行删除时必须提交，任务或文件状态变化后会失效。
  - `totals`：文件总数、将删除数、保留数、已删除数、跳过数等。
  - `files`：逐文件决策；可安全删除的本地文件返回 `action=delete`，被其他任务引用、已删除、pending upload、缺少 object key 或暂不支持的存储返回 `action=keep`。
  - `safety`：预览阶段 `physical_delete_executed=false`、`metadata_mutated=false`、`audit_events_written=false`。

### `POST /api/v1/document-jobs/{job_id}/delete`

- 用途：Admin-only 执行任务删除；这是显式删除端点，不复用 `DELETE /api/v1/document-jobs/{job_id}` 的归档语义。
- 前端约束：operator 不展示该入口；admin 必须先完成 preview 并在确认弹窗中确认删除，执行请求必须携带最新 `preview_hash`。`reason` 和 `confirmation` 仅为兼容旧客户端保留。
- 请求体：

| 字段 | 必填 | 说明 |
|---|---|---|
| `reason` | 否 | 删除原因；为空时使用默认审计原因 `admin_preview_confirm_delete`。 |
| `confirmation` | 否 | 旧客户端可继续提交，提交时必须等于预览返回的 `confirmation_phrase`。 |
| `preview_hash` | 是 | 必须等于最新预览返回的 `preview_hash`。 |

- 行为：
  - 将任务标记为 `deleted_at` / `deleted_by` / `delete_reason`，默认列表隐藏该任务。
  - 保留任务 metadata、事件和 audit evidence；详情接口仍可读取。
  - 清理只属于该任务且可安全删除的 `local_file` / `local_object` 文件，并把成功项 metadata 标记为 `deleted`。
  - 被其他任务引用的 source PDF 会保留。
  - 第一版不执行真实 S3 删除；S3 文件会保留并在响应中暴露 fake/safety contract。
- 成功动作写入 `document_job.delete` audit event，并写入 `job_deleted` 任务事件。
- 删除后的任务不能再下载、重试、clone、取消、归档、取消归档或再次删除；这些接口返回 `409 conflict`。

### 批量请求校验

三个批量接口都会对请求整体做校验：

- `job_ids` 为空：`400 invalid_request`。
- `job_ids` 超过 50 个：`400 invalid_request`。
- `job_ids` 包含重复或空白项：`400 invalid_request`。

通过整体校验后，单个任务的 `404`、`403`、`409` 等错误进入对应 item，不改变批量响应的 `200 OK`。

### `GET /api/v1/document-jobs/{job_id}/download-url`

- 用途：为任务允许的文件生成临时下载链接；默认签发成功完成任务的当前主 DOCX，显式源 PDF 等普通 Artifact 保持原可见性和文件规则。
- 保留 `download_url`、`method=GET`、`expires_at` 和文件安全摘要，additive 返回 `classification`、`warning_code`、`warning_message`。默认和显式当前主件 ID 的分类/警告相同；其他 Artifact 三字段为空，不能误标为主 DOCX。
- blocked/unreviewed/needs_fix 的合法成功主件允许内部下载。文件状态、归属/type、当前性、`expires_at` 和候选隔离等仍在签发前校验；过期文件保持 `409 conflict`，新增 warning 不构成新授权。
- 前端使用当次签发响应显示 internal_only 和适用警告，再打开或展示临时链接，不能只信此前列表缓存。
- 成功签发沿用 `download_authorized` 事件与 `document_job.download_authorize` 审计，记录 generation、file_id、classification、warning_code 的安全摘要，不记录签名 URL、token、正文或对象定位。记录代表授权签发，不证明浏览器已完成下载。
- 本地 HMAC 链接消费时继续重查当前文件；S3 预签名直连受对象、签名和 TTL 控制，不承诺任务状态变化后即时撤销。事件、审计与文件/任务仓储没有跨存储原子事务保证。

### `GET /api/v1/document-jobs/{job_id}/download`

- 用途：使用 `download-url` 返回的短期 token 下载 Word。
- 本地文件缺失返回 404，token 无效或过期返回 403。

## 当前边界

- `direct_pdf_to_word` 是 P0 默认发布路径。
- `en2zh_pdf_to_word` 仍按实验能力处理，不阻塞 P0 direct 发布。
- Golden Sample 当前仍 blocked：正式规模已收敛为 4 个 OPA228 canonical 样本；主链路曾 4/4 通过，但仍等待 admin 人工 Word 质量验收 4/4 通过。
