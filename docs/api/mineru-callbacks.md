---
doc_type: lib-api-ref
entry: mineru-callbacks
category: endpoint
status: current
source_files:
  - app/api/v1/router.py
  - app/domains/jobs/mineru_callbacks_router.py
  - app/api/dependencies.py
  - app/domains/jobs/mineru_callback.py
  - app/domains/document_jobs/execution.py
  - app/domains/document_jobs/schemas.py
  - app/core/config.py
summary: MinerU callback API 提供 document_jobs 的 callback ingress、payload 归一化、checksum 验签和结果 URL 安全校验。
tags: [mineru, callback, api, guards]
last_reviewed: 2026-06-10
---

## 概述

MinerU callback 当前单独挂在 `/api/v1/mineru-callbacks` 下，不和上传入口混在一起。当前入口只服务 `/api/v1/document-jobs` 链路。

这组接口只负责：

- 接收 MinerU callback
- 做 payload 归一化
- 校验 checksum 和 `full_zip_url`
- 匹配 document_job，保存 MinerU 原始结果后继续执行 DocumentIR / Word 生成

callback ingress 本身不做：

- 不替代 `/api/v1/document-jobs`

document_job 收到 `done + full_zip_url` 后会直接保存 MinerU 原始 zip，并继续推进到 DocumentIR / Word 生成。

## 部署模式

| `PUBLIC_DEPLOYMENT_MODE` | 入口要求 |
|---|---|
| `internal` | callback 入口按 checksum 验签 |
| `single_tenant_public` | callback 入口同样按 checksum 验签，不依赖额外 token |

提交给 MinerU 的 URL 直接使用 `MINERU_CALLBACK_URL`。按官方文档，callback 开启后提交任务时必须携带 `seed`，而 callback 请求体会回传 `checksum` 和 `content`。生产 `.env` 推荐至少配置：

```env
MINERU_CALLBACK_URL=https://md2word.962850.xyz/api/v1/mineru-callbacks/result
MINERU_UID=...
```

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

- callback 必须带 `checksum`
- 算法：`sha256(uid + job.mineru_callback_seed + content)`
- `uid` 缺失时会回退 `MINERU_UID`
- job 缺 `mineru_callback_seed` 时返回 `409`
- `uid` 和 `MINERU_UID` 都缺失时返回 `503`

### 结果 URL 规则

若 payload 带 `full_zip_url`，必须同时满足：

- scheme 是 `https`
- host 存在
- host 命中 `MINERU_RESULT_HOST_ALLOWLIST`

### 响应

- 状态码：`200 OK`
- 响应体：`DocumentJobResponse`

注意：

- 这份响应主要表示 callback 已被接受并入队
- document_jobs 的最终结果以随后查询 `GET /api/v1/document-jobs/{job_id}` 为准
- 正常自动链路下，任务可能短暂经过 `parsed`，但最终通常会继续到完成态

## 状态推进

### `done + full_zip_url`

document_jobs：

- 保存 `mineru_raw_result`
- `stage` 从 `parsing` 推进到 `parsed`
- 随后继续执行 DocumentIR 转换、Word 渲染和结果文件登记

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
| `MINERU_UID` 缺失且 payload 也没有 `uid` | `503` | 无法按官方规则校验 checksum |
| checksum 缺失 | `400` | 不接受未签名 callback |
| checksum 错误 | `403` | callback 内容可能被篡改 |
| payload 缺 `batch_id/data_id` | `400` | 无法匹配任务 |
| `content` 不是合法 JSON | `400` | 无法归一化 payload |
| `full_zip_url` 非 `https` | `400` | 不接受不安全结果地址 |
| `full_zip_url` host 不在 allowlist | `400` | 拒绝非白名单结果源 |
| 任务缺 callback seed 却要求 checksum 校验 | `409` | 当前任务状态与 callback 规则不一致 |
| job 不存在 | `404` | `data_id/batch_id` 无法匹配现有任务 |
