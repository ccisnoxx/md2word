---
doc_type: dev-guide
slug: backend-local-minimal-env-and-commands
component: backend-setup
status: current
summary: 当前后端最小 .env 模板和启动命令速查版。
tags: [backend, setup, quickstart, env]
last_reviewed: 2026-05-18
---

## 最小 `.env`

当前仓库根目录 `.env` 最小只需要保证下面这些值：

```env
APP_NAME=md2word_file
APP_ENV=dev
APP_CORS_ORIGINS=http://127.0.0.1:3000,http://localhost:3000
DATA_DIR=data
JOBS_ACCESS_MODE=open
DEFAULT_TRANSLATION_MODE=direct
MINERU_API_TOKEN=
MINERU_MODEL_VERSION=vlm
MINERU_LANGUAGE=en
MINERU_ENABLE_FORMULA=true
MINERU_ENABLE_TABLE=true
MINERU_CALLBACK_URL=
MINERU_UID=
MINERU_CALLBACK_TOKEN=
MINERU_CALLBACK_TOKEN_QUERY_NAME=callback_token
MINERU_RESULT_HOST_ALLOWLIST=mineru.net,cdn-mineru.openxlab.org.cn
PUBLIC_DEPLOYMENT_MODE=internal

OPENAI_BASE_URL=
OPENAI_API_KEY=
OPENAI_MODEL=deepseek-v4-flash
TRANSLATION_MAX_PAGES=20
TRANSLATION_MAX_CHARS=60000
```

说明：

- `MINERU_API_TOKEN` 为空时：
  - `POST /api/v1/jobs/pdf` 不可用
  - `POST /api/v1/jobs` 仍可继续接收 MinerU 输出 zip
- `PUBLIC_DEPLOYMENT_MODE=internal`
  - 本地联调 callback 最省事，不要求 callback token
- 若切到 `PUBLIC_DEPLOYMENT_MODE=single_tenant_public`
  - 需要同时配置 `MINERU_CALLBACK_TOKEN`
  - MinerU 回调时必须带 header 或 query token
- `OPENAI_API_KEY` 为空时：
  - `translation_mode=direct` 仍可用
  - `translation_mode=en2zh` 会被 health 标记为 unavailable，`POST /api/v1/jobs` 也会直接返回 `503`
- `JOBS_ACCESS_MODE=open`
  - 本地联调最省事
- `DATA_DIR`
  - 默认就是仓库内 `data/`

## 最小启动命令

优先使用当前 attention.md 里约定的 conda 环境：

```bash
/Users/sc/miniconda3/envs/md2word/bin/python run_api.py
```

或者：

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## 第一条检查命令

```bash
curl http://127.0.0.1:8000/api/v1/health/ready
```

重点看：

- `jobs_dir_writable`
- `template_docx_exists`
- `layout_config_exists`
- `subscript_config_exists`
- `translation_available`

## 最小联调命令

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/jobs" \
  -F "package=@/path/to/mineru-output.zip" \
  -F "translation_mode=direct"
```

拿到 `job_id` 后：

```bash
curl "http://127.0.0.1:8000/api/v1/jobs/{job_id}"
curl -L "http://127.0.0.1:8000/api/v1/jobs/{job_id}/download/result" -o result.docx
```

如果要验证 PDF 在线提交前半程：

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/jobs/pdf" \
  -F "pdf=@/path/to/source.pdf" \
  -F "translation_mode=direct"
```

如果要本地验证 callback ingress：

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/mineru-callbacks/result" \
  -H "Content-Type: application/json" \
  -d '{"batch_id":"batch_123","content":"{\"batch_id\":\"batch_123\",\"extract_result\":[{\"data_id\":\"job_123\",\"state\":\"done\",\"full_zip_url\":\"https://mineru.net/result.zip\"}]}"}'
```
