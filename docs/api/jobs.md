---
doc_type: lib-api-ref
entry: jobs
category: endpoint
status: current
source_files:
  - app/api/v1/router.py
  - app/api/v1/routers/jobs.py
  - app/api/dependencies.py
  - app/services/jobs/command.py
  - app/services/jobs/lifecycle.py
  - app/services/jobs/query.py
  - app/services/jobs/stage.py
  - app/services/jobs/artifacts.py
  - app/repositories/file_job_repository.py
  - app/schemas/api_v1.py
summary: Jobs API 提供 MinerU zip 后处理、原始 PDF 在线提交、任务查询、产物下载和本地运维动作。
tags: [jobs, api, delivery]
last_reviewed: 2026-05-28
---

## 概述

Jobs API 统一挂在 `/api/v1/jobs` 下，是当前后端的主业务入口。它负责：

- 上传 MinerU 输出 zip 并创建转换任务
- 上传原始 PDF 并提交 MinerU
- 查询任务状态、事件和已登记产物
- 下载原始输入包和最终 DOCX
- 本地运维动作：`retry`、`cancel`、`cleanup-local-files`

当前 `retry/cancel/cleanup-local-files` 按普通 jobs 访问口径开放，不要求 `X-Admin-Token`。如果后续要收紧权限，改 `require_job_ops_access()` 即可。  
MinerU callback 不在这组路由下，单独见 [mineru-callbacks.md](/Users/sc/MinerU/md2word_file/docs/api/mineru-callbacks.md)。

## 普通 jobs 访问模式

| `JOBS_ACCESS_MODE` | 调用要求 |
|---|---|
| `open` | 不需要额外请求头 |
| `token` | 需要 `X-Jobs-Token: ${JOBS_ACCESS_TOKEN}` |
| `admin` | 需要 `X-Admin-Token: ${ADMIN_TOKEN}` |

## 枚举

### `translation_mode`

| 值 | 含义 |
|---|---|
| `direct` | 直接生成当前语言的 DOCX |
| `en2zh` | 先走英文转中文翻译，再生成 DOCX |

### `status`

可用值：`uploaded`、`queued`、`submitting`、`parsing`、`parsed`、`converting`、`completed`、`failed`、`canceled`。

说明：

- `parsed` 仍保留，但在 PDF 在线链路里它现在更像内部里程碑
- 当 callback 命中 `done + full_zip_url` 时，job 通常会继续自动推进到 `completed`
- 因此外部调用方不应再假设“callback 成功后一定稳定停在 `parsed`”
- `parsed` 作为对外 status 枚举短期保留，但它是瞬时可观察状态，不是等待人工处理的稳定状态

## API 参考

### `POST /api/v1/jobs`

- 用途：上传 MinerU 输出 zip 并创建任务。
- 请求体：`multipart/form-data`

| 参数 | 必填 | 说明 |
|---|---|---|
| `package` | 是 | MinerU 输出 zip |
| `template_id` | 否 | 任意可见且启用的模板 ID；留空时回退到当前运行态默认模板 |
| `translation_mode` | 否 | `direct` / `en2zh` |
| `document_language` | 否 | `auto` / `zh` / `en` |
| `use_mineru_header_footer` | 否 | 是否覆盖模板页眉页脚 |

- 响应：`201 Created`

```json
{
  "job_id": "job_123",
  "trace_id": "trace_123",
  "status": "uploaded",
  "translation_mode": "direct"
}
```

- 关键行为：
  - 文件名必须以 `.zip` 结尾
  - 文件大小不能超过 `JOBS_UPLOAD_MAX_BYTES`
  - 上传包必须是合法 zip
  - 当 `translation_mode=en2zh` 时，会先检查当前实例翻译能力是否可用；若 `OPENAI_API_KEY` 或 prompt 缺失，接口直接返回 `503`
  - 响应返回后会通过 `BackgroundTasks` 推进 `convert_package`

### `POST /api/v1/jobs/pdf`

- 用途：上传原始 PDF，并在后台提交到 MinerU。
- 请求体：`multipart/form-data`

| 参数 | 必填 | 说明 |
|---|---|---|
| `pdf` | 是 | 原始 PDF 文件 |
| `template_id` | 否 | 任意可见且启用的模板 ID；留空时回退到当前运行态默认模板 |
| `translation_mode` | 否 | `direct` / `en2zh` |
| `document_language` | 否 | `auto` / `zh` / `en` |
| `use_mineru_header_footer` | 否 | 是否覆盖模板页眉页脚 |

- 响应：`201 Created`
- 关键行为：
  - 文件名必须以 `.pdf` 结尾
  - 若 `content-type` 存在，只接受 `application/pdf` / `application/x-pdf`
  - 文件头必须是 `%PDF-`
  - 必须预先配置 `MINERU_API_TOKEN`
  - 响应返回后会通过 `BackgroundTasks` 推进 `submit_to_mineru`
  - `submit_to_mineru` 成功后任务先进入 `parsing`
  - 当随后 callback 命中 `done + full_zip_url` 时，服务会自动：
    - 恢复远端结果 zip 到本地 `parsed_result_package`
    - 继续走后处理 conversion
    - 最终把任务推进到 `completed` 或 `failed`

### `GET /api/v1/jobs`

- 用途：分页查询任务列表。
- 查询参数：

| 参数 | 默认值 | 说明 |
|---|---|---|
| `page` | `1` | 从 `1` 开始 |
| `page_size` | `20` | 当前限制 `1-100` |
| `status` | 无 | 按状态过滤 |
| `q` | 无 | 按 `job_id` 或 `source_filename` 模糊搜索 |
| `sort` | `created_at_desc` | `created_at_desc/created_at_asc/updated_at_desc/updated_at_asc` |

### `GET /api/v1/jobs/{job_id}`

- 用途：查询单个任务详情。
- 响应：`JobDetailResponse`
  - 包含任务字段、文件列表、事件列表、错误码和完成状态
  - 对 PDF 在线提交任务，详情里还会带：
    - `source_kind`
    - `mineru_batch_id`
    - `mineru_data_id`
    - `mineru_callback_seed`
    - `mineru_status`
    - `mineru_result_zip_url`
  - 这些 `mineru_*` 字段当前仍对外返回，但内部已经被视为 `source_pdf_context` 的兼容投影

### `GET /api/v1/jobs/{job_id}/files`

- 用途：列出当前任务的已登记产物。
- 当前内建产物类型：
  - `source_package`
  - `source_pdf`
  - `parsed_result_package`
  - `translation_request`
  - `result_docx`
- `parsed_result_package` 是受支持的中间产物，表示 MinerU 远端结果 zip 的本地恢复副本；它可用于排障、复现和回溯，但默认交付物仍是 `result_docx`

### `GET /api/v1/jobs/{job_id}/events`

- 用途：查看任务事件流。
- 典型事件：
  - `job_created`
  - `stage_enqueued`
  - `conversion_started`
  - `parsed_result_conversion_started`
  - `parsed_result_package_recovered`
  - `mineru_submit_started`
  - `mineru_submit_succeeded`
  - `mineru_submit_failed`
  - `mineru_callback_received`
  - `mineru_callback_processed`
  - `mineru_callback_failed`
  - `translation_started`
  - `translation_completed`
  - `translation_failed`
  - `job_completed`
  - `job_failed`
  - `job_retry_requested`
  - `job_canceled`
  - `cleanup_local_files`

### `GET /api/v1/jobs/{job_id}/result`

- 用途：返回最终 DOCX 的交付描述。
- 常见状态：
  - `404`：任务不存在
  - `409`：任务尚未完成或还未登记 `result_docx`

### `GET /api/v1/jobs/{job_id}/download/{artifact_alias}`

- 用途：下载已登记产物。
- 当前支持：

| `artifact_alias` | 对应产物 |
|---|---|
| `source-package` | `source_package` |
| `source-pdf` | `source_pdf` |
| `parsed-result-package` | `parsed_result_package` |
| `translation-request` | `translation_request` |
| `result` | `result_docx` |

- 合同说明：
  - `path` 是 job 内逻辑路径，不是本地绝对路径
  - 真正可消费的入口是 `download_url`
  - 本地绝对路径只在服务端内部推导，不对外承诺
  - `parsed-result-package` 是正式支持的中间 artifact 下载入口，但调用方不应把它当作最终 Word 交付物

### `POST /api/v1/jobs/{job_id}/retry`

- 用途：重新调度 `failed` 或 `canceled` 任务。
- 请求体：`multipart/form-data`

| 参数 | 必填 | 说明 |
|---|---|---|
| `reason` | 是 | 重试原因 |

- 响应：

```json
{
  "job_id": "job_123",
  "operation": "retry",
  "accepted": true,
  "status": "queued",
  "message": "任务已重新加入后台执行队列。"
}
```

### `POST /api/v1/jobs/{job_id}/cancel`

- 用途：取消 `uploaded` 或 `queued` 任务。
- 请求体：`multipart/form-data`

| 参数 | 必填 | 说明 |
|---|---|---|
| `reason` | 是 | 取消原因 |

- 约束：
  - `converting` 中的任务当前不支持中断式取消，返回 `409`
  - `completed/failed/canceled` 任务不能重复取消

### `POST /api/v1/jobs/{job_id}/cleanup-local-files`

- 用途：清理单个已完成任务的本地运行态目录。
- 请求体：`multipart/form-data`

| 参数 | 必填 | 说明 |
|---|---|---|
| `reason` | 是 | 清理原因 |

- 当前策略：
  - 删除未登记的运行态目录，例如 `work/`
  - 保留已登记产物，例如 `input/source.zip`、`output/result.docx`
  - 因为当前本地文件还是唯一副本，不能贸然删除已登记产物

## 常见错误

| 场景 | 状态码 | 说明 |
|---|---|---|
| 上传文件不是 zip | `400` | 扩展名或 zip 校验失败 |
| 上传 PDF 非法 | `400` | 扩展名、content-type 或 `%PDF-` 文件头校验失败 |
| `POST /jobs/pdf` 时缺 `MINERU_API_TOKEN` | `503` | PDF 在线解析当前不可用 |
| `translation_mode=en2zh` 但翻译能力不可用 | `503` | 例如 `OPENAI_API_KEY` 未配置 |
| 上传大小超限 | `413` | 超过 `JOBS_UPLOAD_MAX_BYTES` |
| 任务不存在 | `404` | `job_id` 无效 |
| 结果未就绪 | `409` | 任务未完成，或未登记目标产物 |
| 当前状态不允许 retry/cancel/cleanup | `409` | 生命周期约束不满足 |
