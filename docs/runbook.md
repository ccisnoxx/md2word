---
doc_type: dev-guide
slug: runbook
component: backend-runbook
status: current
summary: 当前后端本地联调、运维动作和真实样例验证的运行说明。
tags: [backend, runbook, jobs, local]
last_reviewed: 2026-05-18
---

# 本地运行与联调说明

## 1. 启动服务

```bash
/Users/sc/miniconda3/envs/md2word/bin/python run_api.py
```

默认监听：

```text
http://127.0.0.1:8000
```

## 2. 健康检查

```bash
curl http://127.0.0.1:8000/api/v1/health/live
curl http://127.0.0.1:8000/api/v1/health/ready
```

## 3. 上传 MinerU 输出 zip

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/jobs" \
  -F "package=@/path/to/mineru-output.zip" \
  -F "translation_mode=direct"
```

如果要走翻译：

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/jobs" \
  -F "package=@/path/to/mineru-output.zip" \
  -F "translation_mode=en2zh"
```

前提：

- `GET /api/v1/health/ready` 里的 `translation_available=true`
- `translation_prompt_exists=true`

## 3.1 上传原始 PDF 并提交 MinerU

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/jobs/pdf" \
  -F "pdf=@/path/to/source.pdf" \
  -F "translation_mode=direct"
```

前提：

- `GET /api/v1/health/ready` 里的 `mineru_api_token_configured=true`

当前这条链路会先做到：

- 创建 job
- 登记 `source_pdf`
- 后台提交 MinerU
- 任务进入 `parsing`

接下来 callback 命中 `done + full_zip_url` 后，会自动继续：

- 恢复远端结果 zip 到本地 `parsed_result_package`
- 继续走后处理 conversion
- 最终把任务推进到 `completed` 或 `failed`

## 3.2 本地回放 MinerU callback

先拿到上一步 PDF 任务的 `job_id` 和详情里的 `mineru_batch_id`：

```bash
curl "http://127.0.0.1:8000/api/v1/jobs/{job_id}"
```

然后发送 callback：

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/mineru-callbacks/result" \
  -H "Content-Type: application/json" \
  -d '{"batch_id":"batch_test_001","content":"{\"batch_id\":\"batch_test_001\",\"extract_result\":[{\"data_id\":\"job_123\",\"state\":\"done\",\"full_zip_url\":\"https://mineru.net/result.zip\"}]}"}'
```

预期：

- `GET /api/v1/jobs/{job_id}` 通常会继续推进到 `completed`
- `mineru_result_zip_url` 已持久化
- `files` 里会新增 `parsed_result_package`
- `events` 里出现：
  - `mineru_callback_received`
  - `mineru_callback_processed`
  - `parsed_result_package_recovered`
  - `job_completed`

如果要模拟失败回调，把 `state` 改成 `failed`。预期是：

- `status=failed`
- `error_code=mineru_failed`

## 4. 查询任务与下载结果

```bash
curl "http://127.0.0.1:8000/api/v1/jobs/{job_id}"
curl "http://127.0.0.1:8000/api/v1/jobs/{job_id}/files"
curl "http://127.0.0.1:8000/api/v1/jobs/{job_id}/events"
curl -L "http://127.0.0.1:8000/api/v1/jobs/{job_id}/download/result" -o result.docx
```

如果是 `en2zh`，`events` 里会多出：

- `translation_started`
- `translation_completed`
- 失败时的 `translation_failed`

## 4.1 查询默认模板和配置元数据

```bash
curl "http://127.0.0.1:8000/api/v1/templates"
curl "http://127.0.0.1:8000/api/v1/templates/default"
curl -L "http://127.0.0.1:8000/api/v1/templates/default/download" -o template.docx
```

当前 `templates` 只读接口会返回：

- 默认 DOCX 模板元数据
- `datasheet_template.yaml` 元数据
- `subscripts_dictionary.yaml` 元数据

## 5. 本地运维动作

### retry

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/jobs/{job_id}/retry" \
  -F "reason=rerun"
```

### cancel

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/jobs/{job_id}/cancel" \
  -F "reason=stop"
```

### cleanup-local-files

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/jobs/{job_id}/cleanup-local-files" \
  -F "reason=cleanup"
```

注意：

- `cleanup-local-files` 当前只删未登记的运行态目录，例如 `work/`
- `input/source.zip` 和 `output/result.docx` 会保留，因为它们还是唯一副本

## 6. 真实样例联调口径

当前本地已经验证过一条真实样例链路：

- 样例目录：`/Users/sc/MinerU/OPA228_P1.pdf-d1491424-9662-411d-8e39-fa6bcbd785a4`
- 打包 zip：`/private/tmp/opa228_mineru_sample.zip`
- 实际成功任务：`job_d93a9b69f751`

这条链路已经证明：

- `POST /api/v1/jobs` 可接收真实 MinerU zip
- 后台 stage 能推进到 `completed`
- `download/result` 能得到有效 DOCX

当前 PDF 在线提交能力只做到了对象级测试验证：

- 合法 PDF 可进入 `parsing`
- 缺 `MINERU_API_TOKEN` 时 `POST /api/v1/jobs/pdf` 返回 `503`
- MinerU 提交失败时任务进入 `failed` 且 `error_code=mineru_submit_failed`
- 合法 callback 可自动继续推进到 `completed`
- 非法 `full_zip_url` 会被 callback ingress 直接以 `400` 拒绝
