---
doc_type: integration-guide
slug: pdf-to-word-p0-integration-guide
component: pdf-to-word-backend
status: current
summary: 内部人员按步骤完成 PDF 上传、建任务、查状态、下载和排错。
tags: [integration, pdf, word, api, worker]
last_reviewed: 2026-06-17
---

# PDF 到 Word P0 内部联调说明

## 前置条件

- API 已在 hostdzire 启动；部署机本机默认使用 `http://127.0.0.1:${MD2WORD_API_BIND_PORT:-18000}`，公网入口使用 `https://md2word.962850.xyz`。
- Worker 已启动：Docker 使用 `worker` 服务。
- P0 发布/准生产验收必须使用 MySQL metadata + Redis/Celery；本地 metadata backend 和本地前后端 smoke 不满足 `/health/ready` 的 P0 release gate。
- `AUTH_JWT_SECRET_KEY` 和 `AUTH_INTERNAL_USERS_FILE` 已配置。
- `MINERU_API_TOKEN` 已配置，否则任务会停在解析失败或无法完成。

在 hostdzire 上先设置：

```bash
export API_BASE_URL="http://127.0.0.1:${MD2WORD_API_BIND_PORT:-18000}"
```

从本机或其他外部网络验证公网入口时，把 `API_BASE_URL` 改为 `https://md2word.962850.xyz`。完整发布证据按 [线上优先验证流程](/Users/sc/PycharmProjects/md2word/docs/deploy/online-first-validation-workflow.md) 收集。

## 1. 登录

```bash
TOKEN=$(
  curl -sS -X POST "${API_BASE_URL}/api/v1/auth/login" \
    -H "Content-Type: application/json" \
    -d '{"username":"operator","password":"<password>"}' \
  | python -c "import json,sys; print(json.load(sys.stdin)['access_token'])"
)
```

检查当前账号：

```bash
curl -sS "${API_BASE_URL}/api/v1/auth/me" \
  -H "Authorization: Bearer ${TOKEN}"
```

## 2. 获取上传授权

```bash
PDF=/absolute/path/to/sample.pdf
PDF_NAME=$(basename "${PDF}")
PDF_SIZE=$(wc -c < "${PDF}" | tr -d ' ')
PDF_SHA256=$(shasum -a 256 "${PDF}" | awk '{print "sha256:"$1}')

UPLOAD_JSON=$(
  curl -sS -X POST "${API_BASE_URL}/api/v1/files/upload-url" \
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
  curl -sS -X POST "${API_BASE_URL}/api/v1/document-jobs" \
    -H "Authorization: Bearer ${TOKEN}" \
    -H "Content-Type: application/json" \
    -d "{\"source_file_id\":\"${FILE_ID}\",\"mode\":\"direct_pdf_to_word\",\"document_language\":\"zh\"}"
)

JOB_ID=$(printf '%s' "${JOB_JSON}" | python -c "import json,sys; print(json.load(sys.stdin)['job_id'])")
```

## 5. 查询状态和事件

```bash
curl -sS "${API_BASE_URL}/api/v1/document-jobs/${JOB_ID}" \
  -H "Authorization: Bearer ${TOKEN}"

curl -sS "${API_BASE_URL}/api/v1/document-jobs/${JOB_ID}/events" \
  -H "Authorization: Bearer ${TOKEN}"
```

成功任务的最终状态应为：

```json
{"status":"succeeded","stage":"completed","progress":100}
```

## 6. 下载 Word

```bash
DOWNLOAD_JSON=$(
  curl -sS "${API_BASE_URL}/api/v1/document-jobs/${JOB_ID}/download-url" \
    -H "Authorization: Bearer ${TOKEN}"
)

DOWNLOAD_URL=$(printf '%s' "${DOWNLOAD_JSON}" | python -c "import json,sys; print(json.load(sys.stdin)['download_url'])")
curl -L "${DOWNLOAD_URL}" -o result.docx
```

打开 `result.docx`，确认文件可打开、可编辑，正文、标题、参数表和关键图片符合样本验收记录。

## 7. Golden Sample 批量回归

当前 P0 阻塞验收使用 `tests/fixtures/golden_samples/pdfs/` 下 4 个 OPA228 canonical 样本：`gs-003`、`gs-004`、`gs-006`、`gs-008`。这 4 个样本已覆盖当前 P0 的 datasheet 版式、表格、符号和列表主风险，不以扩展到 10-20 份作为通过条件；样本来源、reviewer 和最终签字由 admin 负责。先做预检：

```bash
GOLDEN_SAMPLE_USERNAME=admin \
GOLDEN_SAMPLE_PASSWORD='<password>' \
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/run_golden_sample_regression.py \
  --preflight \
  --preflight-output tests/tmp/golden_sample_runs/preflight.json
```

`--preflight` 会检查 4 个 PDF 是否齐全、Golden Sample 登录凭据是否配置、`/health/ready` 是否可访问，以及运行时是否满足 MySQL metadata + Celery worker + `p0_document_jobs_ready=true`。预检通过后再执行真实回归：

```bash
GOLDEN_SAMPLE_USERNAME=admin \
GOLDEN_SAMPLE_PASSWORD='<password>' \
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/run_golden_sample_regression.py
```

脚本会在 `tests/tmp/golden_sample_runs/{timestamp}/` 写入 `report.json`、`report.md` 和 `manual-signoff-template.yaml`，并下载成功样本的 Word 文件。报告会列出可编辑内容证据、疑似整页截图样本数、Heading/numbering/表格、疑似标题未样式化、手写列表符号、纯文本 TOC、TOC 点线制表位、宽表、landscape section、表头重复、防跨页断行、表格单元格零段前后距和 LaTeX 残留等机器线索，并把明确机器风险汇总为 DOCX quality flags，例如 `docx_no_editable_content`、`docx_image_only_suspected`、`docx_latex_residue:{count}`、`docx_manual_list_markers:{count}`、`docx_plain_toc_entries:{count}`、`docx_unstyled_heading_candidates:{count}` 和 `docx_wide_table_without_landscape:{count}`。这些 flags 只用于提示 admin 重点复核，不替代人工签字。P0 通过需要 4/4 主链路成功、4/4 DOCX 可打开，并由 admin 按人工验收模板确认 4/4 接近原版排版且符合 Word 文档排版标准。

Golden Sample 阻塞验收要求回归执行账号满足 `GOLDEN_SAMPLE_REQUIRED_ROLE=admin`，默认值即为 `admin`。Admin reviewer 完成人工检查后，把 `manual-signoff-template.yaml` 复制为同目录的 `manual-signoff.yaml`，填写 `reviewer`、`signed_at`、`final_signoff: true`，并把 4 个样本 `verdict` 都设为 `pass`。人工质量判断需要接近原版排版并符合 Word 文档排版标准；当像素级还原和可维护 Word 结构冲突时，以 Word 标准结构为更高优先级。然后对同一个 run_dir 应用签字，不重新跑样本：

```bash
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/run_golden_sample_regression.py \
  --apply-manual-signoff tests/tmp/golden_sample_runs/<run_id>
```

脚本会校验 `reviewer_role=admin`、`job_id`、`filename`、`docx_sha256` 和 4 个样本 verdict。只有自动链路达标且签字校验通过时，`report.json` / `report.md` 中的 `p0_release_ready` 才能变成 `true`。

## 排错速查

| 现象 | 优先检查 |
|---|---|
| `auth_unconfigured` | `AUTH_JWT_SECRET_KEY`、`AUTH_INTERNAL_USERS_FILE` 或兼容入口 `AUTH_INTERNAL_USERS_JSON` |
| `file_too_large` | `JOBS_UPLOAD_MAX_BYTES` 和 PDF 实际大小 |
| `invalid_pdf` 或页数超限 | PDF 是否可读、`PDF_UPLOAD_MAX_PAGES` |
| 任务停在 `queued` | Worker 是否启动、Redis broker 是否连通 |
| `mineru_failed` | `MINERU_API_TOKEN`、MinerU 网络、result host allowlist |
| `render_failed` | IR 内容、模板 docx、模板配置包 |
| 下载返回 `conflict` | 任务尚未 `succeeded` |
