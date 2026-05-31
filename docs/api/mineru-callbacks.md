---
doc_type: lib-api-ref
entry: mineru-callbacks
category: endpoint
status: current
source_files:
  - app/api/v1/router.py
  - app/domains/jobs/mineru_callbacks_router.py
  - app/api/dependencies.py
  - app/domains/jobs/command.py
  - app/domains/jobs/stage.py
  - app/domains/jobs/mineru_callback.py
  - app/domains/jobs/schemas.py
  - app/core/config.py
summary: MinerU callback API 提供 callback ingress、payload 归一化、鉴权和结果 URL 安全校验。
tags: [mineru, callback, api, guards]
last_reviewed: 2026-05-31
---

## 概述

MinerU callback 当前单独挂在 `/api/v1/mineru-callbacks` 下，不和 jobs 上传入口混在一起。

这组接口只负责：

- 接收 MinerU callback
- 做 internal / public 模式鉴权
- 做 payload 归一化
- 校验 checksum 和 `full_zip_url`
- 匹配 job 并入队 `process_callback`

callback ingress 本身不做：

- 不下载结果 zip
- 不生成 DOCX
- 不替代 `/api/v1/jobs/pdf`

但 `process_callback` 成功处理 `done + full_zip_url` 后，后台 workflow 会自动继续恢复 `parsed_result_package` 并推进后处理 conversion。

## 部署模式

| `PUBLIC_DEPLOYMENT_MODE` | 入口要求 |
|---|---|
| `internal` | 不要求 callback token |
| `single_tenant_public` | 要求 `X-MinerU-Callback-Token` 或 query token |

query token 键名由 `MINERU_CALLBACK_TOKEN_QUERY_NAME` 控制，默认是 `callback_token`。

## `POST /api/v1/mineru-callbacks/result`

- 用途：接收 MinerU callback，并把结果推进到 `failed`，或在 `done + full_zip_url` 时自动继续在线后处理链，最终到 `completed`。
- 请求体：`application/json`

### 原始 payload 形态

常见 payload 形态：

```json
{
  "uid": "mineru-user-1",
  "batch_id": "batch_123",
  "checksum": "sha256...",
  "content": "{\"batch_id\":\"batch_123\",\"extract_result\":[{\"data_id\":\"job_123\",\"state\":\"done\",\"full_zip_url\":\"https://mineru.net/result.zip\"}]}"
}
```

### 归一化规则

服务端会把 callback payload 归一化为至少包含下面字段的内部字典：

```json
{
  "batch_id": "batch_123",
  "data_id": "job_123",
  "state": "done",
  "full_zip_url": "https://mineru.net/result.zip",
  "data": {
    "batch_id": "batch_123",
    "extract_result": [
      {
        "data_id": "job_123",
        "state": "done",
        "full_zip_url": "https://mineru.net/result.zip"
      }
    ]
  }
}
```

来源优先级：

- 先读顶层 `batch_id/data_id/state/full_zip_url`
- 若顶层缺失，再从 `content` 里的 JSON 对象回填
- 若 `extract_result[0]` 存在，再从第一项回填 `data_id/state/full_zip_url`

### 任务匹配规则

- 先按 `data_id`
- 再按 `batch_id`

### Checksum 规则

- 只有 payload 带 `checksum` 时才做校验
- 算法：`sha256(uid + job.mineru_callback_seed + content)`
- `uid` 缺失时会回退 `MINERU_UID`
- job 缺 `mineru_callback_seed` 时返回 `409`

### 结果 URL 规则

若 payload 带 `full_zip_url`，必须同时满足：

- scheme 是 `https`
- host 存在
- host 命中 `MINERU_RESULT_HOST_ALLOWLIST`

### 响应

- 状态码：`200 OK`
- 响应体：`JobDetailResponse`

注意：

- 这份响应主要表示 callback 已被接受并入队
- 真正的最终结果应以随后查询 `GET /api/v1/jobs/{job_id}` 为准
- 正常自动链路下，job 可能短暂经过 `parsed`，但最终通常会继续到 `completed`

## 状态推进

### `done + full_zip_url`

- 持久化 `mineru_result_zip_url`
- `status` 通常会继续推进到 `completed`
- `mineru_status -> done`
- `parsed_result_package` 会作为受支持的中间 artifact 登记，可通过 jobs 下载接口按 `parsed-result-package` alias 下载
- 追加事件：
  - `mineru_callback_received`
  - `mineru_callback_processed`
  - `parsed_result_package_recovered`
  - `job_completed`

### `failed`

- `status -> failed`
- `error_code -> mineru_failed`
- `mineru_status -> failed`
- 追加事件：
  - `mineru_callback_received`
  - `mineru_callback_failed`

### 其他 state

- 保持当前 job 主状态不变，一般仍为 `parsing`
- 仅更新 `mineru_status`

## 常见错误

| 场景 | 状态码 | 说明 |
|---|---|---|
| 公开模式但 `MINERU_CALLBACK_TOKEN` 未配置 | `503` | 当前实例不接受公开 callback |
| callback token 错误 | `403` | header/query token 校验失败 |
| checksum 错误 | `403` | callback 内容可能被篡改 |
| payload 缺 `batch_id/data_id` | `400` | 无法匹配任务 |
| `content` 不是合法 JSON | `400` | 无法归一化 payload |
| `full_zip_url` 非 `https` | `400` | 不接受不安全结果地址 |
| `full_zip_url` host 不在 allowlist | `400` | 拒绝非白名单结果源 |
| 任务缺 callback seed 却要求 checksum 校验 | `409` | 当前任务状态与 callback 规则不一致 |
| job 不存在 | `404` | `data_id/batch_id` 无法匹配现有任务 |
