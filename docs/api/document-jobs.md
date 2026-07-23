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
last_reviewed: 2026-07-23
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

## 枚举

### `mode`

| 值 | 含义 |
|---|---|
| `direct_pdf_to_word` | P0 默认路径，直接生成 Word。 |
| `en2zh_pdf_to_word` | 实验能力，先翻译 DocumentIR 再生成 Word。 |
| `ru2zh_pdf_to_word` | 俄译中能力，先翻译 DocumentIR 再生成 Word。 |
| `zh2en_pdf_to_word` | 中译英能力，先翻译 DocumentIR 再生成 Word。 |
| `zh2ru_pdf_to_word` | 中译俄能力，先翻译 DocumentIR 再生成 Word。 |

### 失败诊断字段

失败任务会在详情中返回：

- `failed_stage`
- `error_code`
- `error_message`

前端和联调脚本应优先用这三个字段定位上传、解析、IR、渲染或对象存储问题。

### `translation_qa_status`

| 值 | 含义 |
|---|---|
| `unreviewed` | 未复核。 |
| `approved` | 已通过。 |
| `needs_fix` | 需要修正或跟进。 |
| `blocked` | 阻塞或无法判断。 |

该状态只用于四种翻译任务 QA。列表筛选传 `translation_qa_status` 时，后端只返回翻译模式且状态匹配的任务，避免把 direct 任务的默认值误当成翻译 QA 待办。

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
| `term_version_id` | 否 | 兼容术语版本字段。 |
| `term_rule_set_id` | 否 | 术语规则集。 |
| `term_rule_set_version` | 否 | 术语规则集版本。 |
| `translation_term_set_id` | 否 | 翻译术语集。 |
| `translation_term_version` | 否 | 翻译术语集版本。 |
| `translation_profile_id` | 否 | 翻译配置 ID；创建任务时可显式选择 published 版本。 |
| `translation_profile_version` | 否 | 翻译配置版本；创建任务时可显式选择 published 版本。 |
| `debug_full_text` | 否 | 是否保留全文调试信息。仅翻译任务支持，且只有 admin 可以开启；默认关闭。 |

- 响应：`201 Created`，包含 `job_id`、`status`、`stage`、`progress` 和完整 `job`。
- 成功动作写入 `document_job.create` audit event。
- Readiness gate：当 `p0_document_jobs_required=true` 且 `p0_document_jobs_ready=false` 时，返回 `503 document_jobs_not_ready`，不会创建 job，也不会把 source file 绑定到 job。
- 权限：已登录创建用户可以在创建任务时绑定 published 资源版本；配置维护、发布、设默认仍走各资源管理接口权限。`debug_full_text` 只有 admin 可以开启。

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
- `available_actions` 是服务端对当前用户和任务状态的操作可用性判断，键包括 `download`、`retry`、`cancel`、`archive`、`unarchive`、`clone`、`delete`。每个 action 返回：

| 字段 | 说明 |
|---|---|
| `enabled` | 当前用户能否执行该动作。 |
| `disabled_reason` | 禁用原因；`enabled=true` 时为 `null`。 |
| `retryable` | 仅用于 `retry` 动作，表示失败是否属于可重试失败；其他动作固定为 `false`。 |

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
- 事件：成功保存会写入 `translation_qa_updated` 任务事件，payload 只包含状态、问题归因、复核人和备注长度，不写入全文正文、prompt、response 或密钥。

### `POST /api/v1/document-jobs/{job_id}/retry`

- 用途：对失败任务重试。
- 请求体可包含 `reason`、`use_latest_term_assets` 和术语资产选择字段。
- 成功动作写入 `document_job.retry` audit event。
- 权限：Operator 只能提交原因并沿用原配置；Admin 可选择使用最新默认术语资产或指定 published 术语资产。Retry 当前不重新绑定模板或翻译配置。
- 边界：Retry 只用于失败任务原地重试，不创建新任务，不等同于 clone。

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
| `translation_term_set_id` / `translation_term_version` | 否 | 仅 `select_published_versions` 下可传，Admin-only。 |
| `translation_profile_id` / `translation_profile_version` | 否 | 仅 `select_published_versions` 下可传，Admin-only。 |
| `debug_full_text` | 否 | 覆盖新任务 debug 全文开关。 |

`debug_full_text=true` 只允许 admin 使用。Operator clone 已开启全文归档的源任务时，若使用 `keep_source_snapshot` 继承该开关，也会被拒绝；应由 admin 创建 P1 QA 样本任务或 clone 任务。

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

- 用途：为成功任务生成临时下载链接。
- 响应包含 `download_url`、`method=GET`、`expires_at` 和文件安全摘要。
- 默认结果文件和显式 `file_id` 下载都会校验文件状态、归属和 `expires_at`；过期文件返回 `409 conflict`。
- 成功动作写入 `document_job.download_authorize` audit event。

### `GET /api/v1/document-jobs/{job_id}/download`

- 用途：使用 `download-url` 返回的短期 token 下载 Word。
- 本地文件缺失返回 404，token 无效或过期返回 403。

## 当前边界

- `direct_pdf_to_word` 是 P0 默认发布路径。
- `en2zh_pdf_to_word` 仍按实验能力处理，不阻塞 P0 direct 发布。
- Golden Sample 当前仍 blocked：正式规模已收敛为 4 个 OPA228 canonical 样本；主链路曾 4/4 通过，但仍等待 admin 人工 Word 质量验收 4/4 通过。
