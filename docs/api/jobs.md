---
doc_type: lib-api-ref
entry: jobs
category: endpoint
status: current
source_files:
  - app/api/v1/router.py
  - app/api/v1/routers/jobs.py
  - app/api/v1/routers/jobs_ingest.py
  - app/api/v1/routers/jobs_query.py
  - app/api/v1/routers/jobs_ops.py
  - app/api/v1/routers/jobs_presenters.py
  - app/api/dependencies.py
  - app/core/audit_models.py
  - app/core/job_models.py
  - app/services/audit.py
  - app/services/jobs/command.py
  - app/services/jobs/lifecycle.py
  - app/services/jobs/query.py
  - app/services/jobs/resource_snapshots.py
  - app/services/jobs/stage.py
  - app/services/jobs/artifacts.py
  - app/clients/mineru_client.py
  - app/repositories/file_job_repository.py
  - app/schemas/api_v1.py
summary: Jobs API 提供 MinerU zip 后处理、原始 PDF 在线提交、任务查询、产物下载、本地运维动作和成功动作审计。
tags: [jobs, api, delivery, audit]
last_reviewed: 2026-05-29
---

## 概述

Jobs API 统一挂在 `/api/v1/jobs` 下，是当前后端的主业务入口。它负责：

- 上传 MinerU 输出 zip 并创建转换任务
- 上传原始 PDF 并提交 MinerU
- 查询任务状态、事件和已登记产物
- 下载原始输入包和最终 DOCX
- 本地运维动作：`retry`、`cancel`、`recover-mineru-result`、`cleanup-local-files`
- 对 artifact 下载、retry、cancel 和 cleanup 成功动作写入 audit event

当前 `retry/cancel/recover-mineru-result/cleanup-local-files` 默认按 `JOBS_OPS_ACCESS_MODE=admin` 收紧，要求 `X-Admin-Token`。如需沿用普通 jobs 访问口径，可显式设置 `JOBS_OPS_ACCESS_MODE=jobs`。
MinerU callback 不在这组路由下，单独见 [mineru-callbacks.md](/Users/sc/MinerU/md2word_file/docs/api/mineru-callbacks.md)。

## 普通 jobs 访问模式

| `JOBS_ACCESS_MODE` | 调用要求 |
|---|---|
| `open` | 不需要额外请求头 |
| `token` | 需要 `X-Jobs-Token: ${JOBS_ACCESS_TOKEN}` |
| `admin` | 需要 `X-Admin-Token: ${ADMIN_TOKEN}` |

`JOBS_OPS_ACCESS_MODE=admin` 时，jobs 运维动作始终只接受 `X-Admin-Token`；`JOBS_OPS_ACCESS_MODE=jobs` 时，运维动作复用上表的普通 jobs 访问模式。

## Actor 与审计

- `JOBS_ACCESS_MODE=open` 下，artifact 下载 audit 写 `actor_role=anonymous`、`actor_id=null`；请求里的 `X-Actor-Id` 不会被采信。
- `JOBS_ACCESS_MODE=token` 下，`X-Jobs-Token` 校验通过后写 `actor_role=jobs`；可选 `X-Actor-Id` 作为操作者标签，缺省为 `jobs-client`。
- `JOBS_ACCESS_MODE=admin` 或 `JOBS_OPS_ACCESS_MODE=admin` 下，`X-Admin-Token` 校验通过后写 `actor_role=admin`；可选 `X-Actor-Id` 作为操作者标签，缺省为 `admin`。
- audit event 只记录成功动作，不记录 token、完整 payload 或本地绝对私密路径。

当前 Jobs API 覆盖的 audit actions：

| 动作 | audit action | target |
|---|---|---|
| artifact 下载 | `artifact.download` | `{job_id}:{artifact_alias}` |
| retry | `job.retry` | `{job_id}` |
| cancel | `job.cancel` | `{job_id}` |
| cleanup-local-files | `job.cleanup_local_files` | `{job_id}` |

`recover-mineru-result` 当前只做 ops 鉴权和 JobEvent 记录，不写 audit event。

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
| `template_version` | 否 | MySQL resource mode 下绑定指定 published Template Version |
| `term_rule_set_id` | 否 | MySQL resource mode 下绑定指定 Term Rule Set；留空时使用默认规则集 |
| `term_rule_set_version` | 否 | MySQL resource mode 下绑定指定 published Term Rule Set Version |
| `translation_profile_id` | 否 | `en2zh` + MySQL resource mode 下绑定指定 Translation Profile |
| `translation_profile_version` | 否 | `en2zh` + MySQL resource mode 下绑定指定 published Translation Profile Version |
| `translation_mode` | 否 | `direct` / `en2zh` |
| `document_language` | 否 | `auto` / `zh` / `en` |
| `use_mineru_header_footer` | 否 | 是否覆盖模板页眉页脚 |

- 响应：`201 Created`

```json
{
  "job_id": "job_123",
  "trace_id": "trace_123",
  "status": "uploaded",
  "translation_mode": "direct",
  "resource_snapshot": null
}
```

- 关键行为：
  - 文件名必须以 `.zip` 结尾
  - 文件大小不能超过 `JOBS_UPLOAD_MAX_BYTES`
  - 上传包必须是合法 zip
  - 当 `translation_mode=en2zh` 时，会先检查当前实例翻译能力是否可用；若 `OPENAI_API_KEY` 或 prompt 缺失，接口直接返回 `503`
  - MySQL resource mode 下会在创建时绑定 `template`、`term_rule_set`、MinerU 配置和可选 `translation_profile` 的不可变 `resource_snapshot`
  - file / sqlite backend 下，显式传 `template_version`、`term_rule_set_id/version` 或 `translation_profile_id/version` 会返回 `503`
  - `direct` 任务不能绑定 Translation Profile；传入 `translation_profile_id` 或 `translation_profile_version` 会返回 `400`
  - `JOBS_WORKER_MODE=in_process` 时响应返回后会通过 `BackgroundTasks` 推进 `convert_package`
  - `JOBS_WORKER_MODE=external` 时响应返回后只入队，后续由 `run_worker.py` 消费 stage message

### `POST /api/v1/jobs/pdf`

- 用途：上传原始 PDF，并在后台提交到 MinerU。
- 请求体：`multipart/form-data`

| 参数 | 必填 | 说明 |
|---|---|---|
| `pdf` | 是 | 原始 PDF 文件 |
| `template_id` | 否 | 任意可见且启用的模板 ID；留空时回退到当前运行态默认模板 |
| `template_version` | 否 | MySQL resource mode 下绑定指定 published Template Version |
| `term_rule_set_id` | 否 | MySQL resource mode 下绑定指定 Term Rule Set；留空时使用默认规则集 |
| `term_rule_set_version` | 否 | MySQL resource mode 下绑定指定 published Term Rule Set Version |
| `translation_profile_id` | 否 | `en2zh` + MySQL resource mode 下绑定指定 Translation Profile |
| `translation_profile_version` | 否 | `en2zh` + MySQL resource mode 下绑定指定 published Translation Profile Version |
| `translation_mode` | 否 | `direct` / `en2zh` |
| `document_language` | 否 | `auto` / `zh` / `en` |
| `use_mineru_header_footer` | 否 | 是否覆盖模板页眉页脚 |

- 响应：`201 Created`
- 关键行为：
  - 文件名必须以 `.pdf` 结尾
  - 若 `content-type` 存在，只接受 `application/pdf` / `application/x-pdf`
  - 文件头必须是 `%PDF-`
  - 必须预先配置 `MINERU_API_TOKEN`
  - `JOBS_WORKER_MODE=in_process` 时响应返回后会通过 `BackgroundTasks` 推进 `submit_to_mineru`
  - `JOBS_WORKER_MODE=external` 时响应返回后只入队，后续由 `run_worker.py` 消费 stage message
  - `submit_to_mineru` 成功后任务先进入 `parsing`
  - MySQL resource mode 下创建时会绑定不可变 `resource_snapshot`；PDF 链路的 MinerU snapshot 还包含非敏感提交配置
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
  - MySQL resource mode 创建的任务会带 `resource_snapshot`，包含 `template`、`term_rule_set`、可选 `translation_profile`、MinerU snapshot 和 artifact id

### `GET /api/v1/jobs/{job_id}/files`

- 用途：列出当前任务的已登记产物。
- 当前内建产物类型：
  - `source_package`
  - `source_pdf`
  - `parsed_result_package`
  - `translation_request`
  - `translation_trace`
  - `result_docx`
- `parsed_result_package` 是受支持的中间产物，表示 MinerU 远端结果 zip 的本地恢复副本；它可用于排障、复现和回溯，但默认交付物仍是 `result_docx`
- 新登记产物会返回 `size_bytes` 和 `sha256`；旧记录如果还没有 fingerprint，这两个字段可能为 `null`

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
  - `mineru_result_polled`
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
| `translation-trace` | `translation_trace` |
| `result` | `result_docx` |

- 合同说明：
  - `path` 是 job 内逻辑路径，不是本地绝对路径
  - `storage_backend=object` 时，`object_key` 是服务端内部对象定位字段；调用方仍不应直接拼接或持久依赖对象地址
  - `size_bytes` 和 `sha256` 是登记时的 artifact fingerprint，`sha256` 格式为 `sha256:<hex>`
  - 真正可消费的入口是 `download_url`
  - 本地绝对路径只在服务端内部推导，不对外承诺
  - 服务端内部下载结果可来自本地文件、流式内容或临时重定向；调用方仍只依赖同一个 `download_url`
  - 本地文件缺失返回 `404`，logical path 越界或不匹配返回 `400`，fingerprint 不匹配返回 `409`
  - `parsed-result-package` 是正式支持的中间 artifact 下载入口，但调用方不应把它当作最终 Word 交付物
  - 成功返回本地文件、流式内容或重定向前会写 `artifact.download` audit event，`target_id={job_id}:{artifact_alias}`

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

- 审计：成功后写 `job.retry` audit event，`reason` 同请求体。

### `POST /api/v1/jobs/{job_id}/cancel`

- 用途：取消 `uploaded` 或 `queued` 任务。
- 请求体：`multipart/form-data`

| 参数 | 必填 | 说明 |
|---|---|---|
| `reason` | 是 | 取消原因 |

- 约束：
  - `converting` 中的任务当前不支持中断式取消，返回 `409`
  - `completed/failed/canceled` 任务不能重复取消
- 审计：成功后写 `job.cancel` audit event，`reason` 同请求体。

### `POST /api/v1/jobs/{job_id}/recover-mineru-result`

- 用途：callback 丢失或长时间未收到时，主动查询 MinerU batch 结果并复用后续 `process_callback` stage。
- 认证：默认 `X-Admin-Token`，受 `JOBS_OPS_ACCESS_MODE` 控制。
- 前置条件：
  - 任务必须是 `source_pdf`
  - 任务必须处于 `parsing`
  - 任务必须已有 `mineru_batch_id`
  - 实例必须配置 `MINERU_API_TOKEN`
- 成功响应：

```json
{
  "job_id": "job_123",
  "operation": "recover-mineru-result",
  "accepted": true,
  "status": "queued",
  "message": "已主动查询 MinerU 结果并进入后台处理。"
}
```

- 关键行为：
  - 调用 MinerU `GET /api/v4/extract-results/batch/{batch_id}` 查询结果
  - 查询结果会归一化成内部 `process_callback` payload
  - `done + full_zip_url` 会继续恢复 `parsed_result_package` 并推进到 DOCX 后处理
  - 会追加 `mineru_result_polled` 事件
  - 当前不写 audit event

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
- 审计：成功后写 `job.cleanup_local_files` audit event，`reason` 同请求体。

## 常见错误

| 场景 | 状态码 | 说明 |
|---|---|---|
| 上传文件不是 zip | `400` | 扩展名或 zip 校验失败 |
| 上传 PDF 非法 | `400` | 扩展名、content-type 或 `%PDF-` 文件头校验失败 |
| `POST /jobs/pdf` 时缺 `MINERU_API_TOKEN` | `503` | PDF 在线解析当前不可用 |
| `translation_mode=en2zh` 但翻译能力不可用 | `503` | 例如 `OPENAI_API_KEY` 未配置 |
| 显式资源版本选择但 backend 不是 MySQL resource mode | `503` | 需要 `JOBS_REPOSITORY_BACKEND=mysql` |
| 指定资源版本不存在 | `404` | 例如 template / term-rule-set / translation-profile version 不存在 |
| 默认资源版本缺失或 snapshot 无法物化 | `409` | 例如 MySQL resource mode 下缺默认 published profile |
| `direct` 任务传 Translation Profile | `400` | `direct` 不解析翻译 profile |
| 上传大小超限 | `413` | 超过 `JOBS_UPLOAD_MAX_BYTES` |
| 任务不存在 | `404` | `job_id` 无效 |
| 结果未就绪 | `409` | 任务未完成，或未登记目标产物 |
| 当前状态不允许 retry/cancel/cleanup | `409` | 生命周期约束不满足 |
