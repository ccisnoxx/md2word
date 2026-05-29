---
doc_type: deploy-guide
slug: p0-docker-deployment
component: pdf-to-word-backend
status: current
summary: P0 API 与 document_jobs Worker 共用镜像的 Docker Compose 部署说明。
tags: [deploy, docker, api, worker, mysql, redis]
last_reviewed: 2026-05-29
---

# P0 Docker 部署说明

## 组件

`docker-compose.p0.yml` 启动 4 个服务：

| 服务 | 作用 |
|---|---|
| `api` | FastAPI，监听容器内 `8000` |
| `worker` | `run_document_worker.py`，消费 `document-jobs` Celery 队列 |
| `redis` | Celery broker/result backend |
| `mysql` | document_files、document_jobs、events、audit metadata |

`api` 和 `worker` 使用同一个镜像 `md2word-p0:latest`，共享 `md2word-data` volume。P0 默认 artifact 使用 `local_object`，因此 API 上传的 PDF 和 Worker 生成的 Word 都在同一个 `/app/data/object_artifacts` 里。

## 环境变量

复制样例并填入真实值：

```bash
cp deploy/p0.env.example deploy/p0.env
```

必须修改：

| 变量 | 说明 |
|---|---|
| `MYSQL_ROOT_PASSWORD` | MySQL root 密码 |
| `JOBS_MYSQL_PASSWORD` | 应用 MySQL 用户密码 |
| `JOBS_ACCESS_TOKEN` | legacy jobs 接口 token |
| `ADMIN_TOKEN` | 运维接口 token |
| `AUTH_JWT_SECRET_KEY` | 内部账号 JWT 签名密钥 |
| `AUTH_INTERNAL_USERS_JSON` | 内部账号 JSON，必须放 password_hash |
| `MINERU_API_TOKEN` | MinerU 在线解析 token |

生成内部账号密码哈希：

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -c "from app.services.auth.service import hash_password; print(hash_password('change-me-password'))"
```

`AUTH_INTERNAL_USERS_JSON` 示例：

```json
{"users":[{"id":"operator-1","username":"operator","password_hash":"pbkdf2_sha256$260000$...","role":"operator","tenant_id":"default","company_id":"default","status":"active"}]}
```

## 启动

```bash
docker compose --env-file deploy/p0.env -f docker-compose.p0.yml build
docker compose --env-file deploy/p0.env -f docker-compose.p0.yml up -d
```

检查：

```bash
curl -sS http://127.0.0.1:8000/api/v1/health/live
curl -sS http://127.0.0.1:8000/api/v1/health/ready
docker compose -f docker-compose.p0.yml ps
docker compose -f docker-compose.p0.yml logs -f api worker
```

停止：

```bash
docker compose -f docker-compose.p0.yml down
```

如需同时删除 MySQL、Redis 和 artifact volume：

```bash
docker compose -f docker-compose.p0.yml down -v
```

## 已知边界

- 当前 compose 是单机 P0 部署，不包含 HTTPS、反向代理、对象存储生命周期规则和外部密钥系统。
- `AUTH_INTERNAL_USERS_JSON` 为空时，`/api/v1/auth/login` 会返回 `auth_unconfigured`。
- `MINERU_API_TOKEN` 为空时，PDF 端到端解析不能完成。
- 如改用 S3/OSS，需要把 `JOBS_ARTIFACT_STORAGE_BACKEND` 改为 `s3` 并补齐 bucket、endpoint、access key、secret 和下载模式。
