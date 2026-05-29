---
doc_type: integration-guide
slug: pdf-to-word-p0-integration-guide
component: pdf-to-word-backend
status: current
summary: 内部人员按步骤完成 PDF 上传、建任务、查状态、下载和排错。
tags: [integration, pdf, word, api, worker]
last_reviewed: 2026-05-29
---

# PDF 到 Word P0 内部联调说明

## 前置条件

- API 已启动，默认地址 `http://127.0.0.1:8000`。
- Worker 已启动：Docker 使用 `worker` 服务，本地使用 `run_document_worker.py`。
- Redis、MySQL 或本地 metadata backend 可用。
- `AUTH_JWT_SECRET_KEY` 和 `AUTH_INTERNAL_USERS_JSON` 已配置。
- `MINERU_API_TOKEN` 已配置，否则任务会停在解析失败或无法完成。

## 1. 登录

```bash
TOKEN=$(
  curl -sS -X POST "http://127.0.0.1:8000/api/v1/auth/login" \
    -H "Content-Type: application/json" \
    -d '{"username":"operator","password":"<password>"}' \
  | python -c "import json,sys; print(json.load(sys.stdin)['access_token'])"
)
```

检查当前账号：

```bash
curl -sS "http://127.0.0.1:8000/api/v1/auth/me" \
  -H "Authorization: Bearer ${TOKEN}"
```

## 2. 获取上传授权

```bash
PDF=/absolute/path/to/sample.pdf
PDF_NAME=$(basename "${PDF}")
PDF_SIZE=$(wc -c < "${PDF}" | tr -d ' ')
PDF_SHA256=$(shasum -a 256 "${PDF}" | awk '{print "sha256:"$1}')

UPLOAD_JSON=$(
  curl -sS -X POST "http://127.0.0.1:8000/api/v1/files/upload-url" \
    -H "Authorization: Bearer ${TOKEN}" \
    -H "Content-Type: application/json" \
    -d "{\"filename\":\"${PDF_NAME}\",\"mime_type\":\"application/pdf\",\"size_bytes\":${PDF_SIZE},\"checksum_sha256\":\"${PDF_SHA256}\"}"
)

FILE_ID=$(printf '%s' "${UPLOAD_JSON}" | python -c "import json,sys; print(json.load(sys.stdin)['file_id'])")
UPLOAD_URL=$(printf '%s' "${UPLOAD_JSON}" | python -c "import json,sys; print(json.load(sys.stdin)['upload_url'])")
```

## 3. 上传 PDF 内容

本地代理上传需要继续带 Bearer token：

```bash
curl -sS -X PUT "${UPLOAD_URL}" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/pdf" \
  --data-binary @"${PDF}"
```

如果 `UPLOAD_URL` 是外部 S3/OSS presigned URL，只带接口返回的 headers，不要额外带 Bearer token。

## 4. 创建任务

```bash
JOB_JSON=$(
  curl -sS -X POST "http://127.0.0.1:8000/api/v1/document-jobs" \
    -H "Authorization: Bearer ${TOKEN}" \
    -H "Content-Type: application/json" \
    -d "{\"source_file_id\":\"${FILE_ID}\",\"mode\":\"direct_pdf_to_word\",\"document_language\":\"zh\"}"
)

JOB_ID=$(printf '%s' "${JOB_JSON}" | python -c "import json,sys; print(json.load(sys.stdin)['job_id'])")
```

## 5. 查询状态和事件

```bash
curl -sS "http://127.0.0.1:8000/api/v1/document-jobs/${JOB_ID}" \
  -H "Authorization: Bearer ${TOKEN}"

curl -sS "http://127.0.0.1:8000/api/v1/document-jobs/${JOB_ID}/events" \
  -H "Authorization: Bearer ${TOKEN}"
```

成功任务的最终状态应为：

```json
{"status":"succeeded","stage":"completed","progress":100}
```

## 6. 下载 Word

```bash
DOWNLOAD_JSON=$(
  curl -sS "http://127.0.0.1:8000/api/v1/document-jobs/${JOB_ID}/download-url" \
    -H "Authorization: Bearer ${TOKEN}"
)

DOWNLOAD_URL=$(printf '%s' "${DOWNLOAD_JSON}" | python -c "import json,sys; print(json.load(sys.stdin)['download_url'])")
curl -L "${DOWNLOAD_URL}" -o result.docx
```

打开 `result.docx`，确认文件可打开、可编辑，正文、标题、参数表和关键图片符合样本验收记录。

## 7. Golden Sample 批量回归

先把业务确认后的 PDF 放到 `tests/golden_samples/pdfs/`，文件名与 `tests/golden_samples/manifest.yaml` 一致，然后执行：

```bash
GOLDEN_SAMPLE_USERNAME=operator \
GOLDEN_SAMPLE_PASSWORD='<password>' \
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/run_golden_sample_regression.py
```

脚本会在 `tests/golden_samples/runs/{timestamp}/` 写入 `report.json` 和 `report.md`，并下载成功样本的 Word 文件。

## 排错速查

| 现象 | 优先检查 |
|---|---|
| `auth_unconfigured` | `AUTH_JWT_SECRET_KEY`、`AUTH_INTERNAL_USERS_JSON` |
| `file_too_large` | `JOBS_UPLOAD_MAX_BYTES` 和 PDF 实际大小 |
| `invalid_pdf` 或页数超限 | PDF 是否可读、`PDF_UPLOAD_MAX_PAGES` |
| 任务停在 `queued` | Worker 是否启动、Redis broker 是否连通 |
| `mineru_failed` | `MINERU_API_TOKEN`、MinerU 网络、result host allowlist |
| `render_failed` | IR 内容、模板 docx、模板配置包 |
| 下载返回 `conflict` | 任务尚未 `succeeded` |
