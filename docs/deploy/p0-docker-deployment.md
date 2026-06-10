---
doc_type: deploy-guide
slug: p0-docker-deployment
component: pdf-to-word-backend
status: current
summary: P0 API 与 document_jobs Worker 共用镜像和根目录 .env 的 Docker Compose 部署说明。
tags: [deploy, docker, api, worker, mysql, redis]
last_reviewed: 2026-05-31
---

# P0 Docker 部署说明

## 组件

`docker/prod/docker-compose.yml` 启动 4 个服务：

| 服务 | 作用 |
|---|---|
| `api` | FastAPI，监听容器内 `8000` |
| `worker` | `scripts/dev/run_document_worker.py`，消费 `document-jobs` Celery 队列 |
| `redis` | Celery broker/result backend |
| `mysql` | document_files、document_jobs、events、audit metadata |

`api` 和 `worker` 使用同一个镜像 `md2word-p0:latest`，共享 `md2word-var` volume。P0 默认 artifact 使用 `local_object`，因此 API 上传的 PDF 和 Worker 生成的 Word 都在同一个 `/app/var/object_artifacts` 里。

建议的线上入口形态是：

- 宿主机 `nginx` 对外监听 `80/443`
- Docker `api` 只绑定 `127.0.0.1:${MD2WORD_API_BIND_PORT}`
- 宿主机 `nginx` 再反代到 `127.0.0.1:${MD2WORD_API_BIND_PORT}`
- 如有前置机，可让前置机通过 WireGuard / 内网把域名流量转发到部署机的 `80/443`

## 环境变量

复制根目录样例并填入真实值：

```bash
cp .env.example .env
```

必须修改：

| 变量 | 说明 |
|---|---|
| `MYSQL_ROOT_PASSWORD` | MySQL root 密码 |
| `JOBS_MYSQL_PASSWORD` | 应用 MySQL 用户密码 |
| `JOBS_ACCESS_TOKEN` | legacy jobs 接口 token |
| `ADMIN_TOKEN` | 运维接口 token |
| `AUTH_JWT_SECRET_KEY` | 内部账号 JWT 签名密钥 |
| `AUTH_INTERNAL_USERS_FILE` | 内部账号 JSON 文件路径，默认 `deploy/auth_internal_users.json` |
| `MINERU_API_TOKEN` | MinerU 在线解析 token |
| `MINERU_CALLBACK_URL` | MinerU 回调基础地址，例如 `https://md2word-api.962850.xyz/api/v1/mineru-callbacks/result` |
| `MINERU_UID` | MinerU 官方 checksum 验签使用的用户 uid |
| `PUBLIC_DEPLOYMENT_MODE` | 公开域名部署设为 `single_tenant_public` |

按 MinerU 官方文档，callback 请求体依赖 `checksum + content`，提交任务时必须同时携带 `seed`。这里不要给 `MINERU_CALLBACK_URL` 追加自定义 token 或 query 参数；服务端会按 `uid + seed + content` 校验 callback。

如果要启用 P1 英译中实验链路，还需要：

| 变量 | 说明 |
|---|---|
| `OPENAI_BASE_URL` | OpenAI-compatible 接口地址 |
| `OPENAI_API_KEY` | OpenAI-compatible provider 密钥 |
| `OPENAI_MODEL` | 翻译模型名 |
| `TRANSLATION_PROVIDER_BACKEND` | 设为 `openai_compatible` |

生成内部账号密码哈希：

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -c "from app.services.auth.service import hash_password; print(hash_password('change-me-password'))"
```

`deploy/auth_internal_users.json` 示例：

```json
{"users":[{"id":"operator-1","username":"operator","password_hash":"pbkdf2_sha256$260000$...","role":"operator","tenant_id":"default","company_id":"default","status":"active"}]}
```

`AUTH_INTERNAL_USERS_JSON` 仍保留为兼容入口，但不建议 Docker 部署使用。PBKDF2 hash 包含 `$`，放在 env 值里容易被 Compose 或 shell 转义；文件读取不会经过 shell 展开。

## 启动

```bash
docker compose --env-file .env -f docker/prod/docker-compose.yml build
docker compose --env-file .env -f docker/prod/docker-compose.yml up -d
```

检查：

```bash
curl -sS http://127.0.0.1:${MD2WORD_API_BIND_PORT:-18000}/api/v1/health/live
curl -sS http://127.0.0.1:${MD2WORD_API_BIND_PORT:-18000}/api/v1/health/ready
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/check_release.py --runtime-url http://127.0.0.1:${MD2WORD_API_BIND_PORT:-18000}
docker compose --env-file .env -f docker/prod/docker-compose.yml ps
docker compose --env-file .env -f docker/prod/docker-compose.yml logs -f api worker
```

`check_release.py --runtime-url` 会读取 `/api/v1/health/ready`，同时检查 `deployment_init_ready` 和 `p0_document_jobs_ready`。公开或生产环境出现 `p0_document_jobs_blockers` 时，不应开放上传入口；常见阻断项是 document_jobs worker backend 未启用、Celery broker/queue 缺失、内部账号未配置、MinerU token/callback/uid 缺失。

停止：

```bash
docker compose --env-file .env -f docker/prod/docker-compose.yml down
```

如需同时删除 MySQL、Redis 和 artifact volume：

```bash
docker compose --env-file .env -f docker/prod/docker-compose.yml down -v
```

## 开发 Compose

本地需要用 Docker 跑完整依赖时，可以使用开发编排：

```bash
docker compose --env-file .env -f docker/dev/docker-compose.yml up -d --build
```

开发编排会把仓库挂载到容器 `/app`，API 使用 `uvicorn --reload`；生产编排则把代码复制进镜像。

## 已知边界

- 当前 compose 是单机 P0 部署，不包含 HTTPS、反向代理、对象存储生命周期规则和外部密钥系统。
- `AUTH_INTERNAL_USERS_FILE` 和 `AUTH_INTERNAL_USERS_JSON` 都为空时，`/api/v1/auth/login` 会返回 `auth_unconfigured`。
- `MINERU_API_TOKEN` 为空时，PDF 端到端解析不能完成。
- `MINERU_CALLBACK_URL` 为空时，MinerU 异步完成不会主动推回；document_jobs 可能停在 `running/parsing` 等待后续重投递或人工排查。
- `MINERU_UID` 为空且 callback payload 也不带 `uid` 时，ready health 会把 `mineru_uid_missing` 标为 blocker。
- 如改用 S3/OSS，需要把 `JOBS_ARTIFACT_STORAGE_BACKEND` 改为 `s3` 并补齐 bucket、endpoint、access key、secret 和下载模式。
