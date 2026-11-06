---
doc_type: deploy-guide
slug: p0-docker-deployment
component: pdf-to-word-backend
status: current
summary: P0 API 与 document_jobs Worker 共用镜像和根目录 .env 的 Docker Compose 部署说明。
tags: [deploy, docker, api, worker, mysql, redis]
last_reviewed: 2026-11-06
---

# P0 Docker 部署说明

## 组件

`docker/prod/docker-compose.yml` 启动 4 个服务：

| 服务 | 作用 |
|---|---|
| `api` | FastAPI，监听容器内 `8000` |
| `worker` | `scripts/dev/run_document_worker.py`，消费 `document-jobs` 和 `document-translation-batches` Celery 队列 |
| `redis` | Celery broker/result backend |
| `mysql` | document_files、document_jobs、events、audit metadata |

生产 `api` 和 `worker` 使用同一个必填的 `MD2WORD_IMAGE` 镜像引用，共享 `md2word-var` volume。每次生产构建使用新的版本化标签，构建一次后供两者复用；正式部署时还应核对两个容器的实际 image ID 相同，不能只比较标签。P0 默认 artifact 使用 `local_object`，因此 API 上传的 PDF 和 Worker 生成的 Word 都在同一个 `/app/var/object_artifacts` 里。

配置中心原子轮换 MinerU 账号 UID 与 API 密钥后会写入 `/app/var/config/mineru_config.json`，同一 volume 中的 API 与 Worker 后续请求立即读取新绑定。运行时文件不存在时仍共同使用 `.env` 的 `MINERU_API_TOKEN` 与 `MINERU_UID`；文件存在后完整绑定始终优先，损坏或缺少任一字段时明确阻断而不会混用环境变量。

建议的线上入口形态是：

- 宿主机 `nginx` 对外监听 `80/443`
- Docker `api` 只绑定 `127.0.0.1:${MD2WORD_API_BIND_PORT}`
- 宿主机 `nginx` 再反代到 `127.0.0.1:${MD2WORD_API_BIND_PORT}`
- 如有前置机，可让前置机通过 WireGuard / 内网把域名流量转发到部署机的 `80/443`

md2word 当前按 [线上优先验证流程](./online-first-validation-workflow.md) 收集发布证据：本地负责改写和不依赖服务的检查，完整 API/Worker/MySQL/Redis/Celery/Golden Sample 验证在 `hostdzire` 执行。

上述线上优先验证流程中使用 `latest`、GitHub archive 后直接构建等镜像构建/回滚命令仅适用于 B02 之前的版本；[hostdzire 部署记录](./hostdzire-dmit-md2word.md) 的发布及回滚步骤已同步 B02 输入。B02 镜像输入、离线 wheelhouse 与 `MD2WORD_IMAGE` 以本文为准，旧线上流程不构成新镜像的构建步骤。获准回退时，应选择已保留的上一版本化镜像身份并核对实际 image ID；没有旧产物时，须按对应旧版配方单独准备，不能复用新标签冒充旧产物。

hostdzire 普通上线使用独立的 `${RELEASE_DIR}`；每个 release 从 GitHub archive 导出运行包，补齐下节的离线 wheelhouse，复制上一版 `.env` 和内部账号 JSON 后 build/up。历史工作树不作为默认上线目录。release 目录不应包含 `.git`、`.idea`、`.codex`、`.agents`、`.trellis`、`.run` 等开发目录。

## 依赖锁与构建输入

首个受验收目标为 **CPython 3.11.18 / Debian 13 trixie / linux/amd64**；开发和生产 Dockerfile 使用同一目标锁与 Python 基础 digest。该锁不声明 macOS、arm64 或其他 Python 版本支持；构建应在对应的 Linux amd64 环境进行。

- `requirements.txt` 保留 15 项直接依赖声明职责；`PyMySQL[rsa]` 显式保留既有 cryptography/cffi/pycparser 能力。
- `requirements/locks/cp311-linux-amd64.txt` 固定 57 项运行依赖及制品 SHA-256，首版对齐目标基线，不隐含升级或降级，包括 python-docx 1.2.0 与 lxml 6.1.3。
- 生成器为 uv 0.11.19。A/B 干净 venv 的工具集合为 pip 24.0、setuptools 79.0.1，未安装 wheel；候选镜像保留固定基础镜像的全局工具 pip 24.0、setuptools 79.0.1、wheel 0.46.3。两种环境均使用 pip 24.0 安装，工具不计入 57 项运行闭包；生产离线目录中的 pip 26.2.2 不用于候选，也不执行无版本 pip 升级。

在导出的构建上下文根目录补齐 `requirements/wheels/`，放入与锁一致的 **57 个运行 wheel，不含 pip 工具**。wheel 二进制不提交 Git，GitHub archive 本身不包含这些制品；缺少该目录时构建会失败。发布准备应按以下来源记录取齐制品，并逐个核对文件名、目标 wheel tags 和 SHA-256：

- [原制品官方 PyPI 对账](../../.trellis/tasks/11-06-dependency-image-baseline/research/pypi-provenance.json)：使用其中除 pip 外的 56 个运行制品。
- [补齐 Pillow 与完整性记录](../../.trellis/tasks/11-06-dependency-image-baseline/research/wheelhouse-provenance.json)：加入其中 `pillow` 记录指定的 Pillow 12.2.0 wheel。

来源记录需随发布准备单独保留，不依赖运行镜像内存在 `.trellis`。这些记录将制品对应到官方 PyPI 文件；只计算本地 hash 不能独立证明来源可信。现有 wheel 的历史下载途径未完整恢复，已核实的是文件身份与官方 hash 的匹配。若缺失、hash 不符或平台不兼容，应停止；不得自动换源、下载其他版本或回退到 sdist 编译。

两个 Dockerfile 将相同锁和 wheelhouse 复制到 `/tmp`，以 `--isolated --no-index --find-links=/tmp/wheels --require-hashes --only-binary=:all:` 安装。安装后删除可见 wheelhouse；先前 COPY 层仍保留 wheel 字节，因此这一步不承诺缩减镜像层体积。

| 组件 | 官方固定引用 | 目标版本 |
|---|---|---|
| Python | `docker.io/library/python:3.11.18-slim-trixie@sha256:b701198cb708b68d9413ca67d6311bd97c9389a2c5fe4da0511fc652642366cd` | CPython 3.11.18，amd64 manifest |
| MySQL | `docker.io/library/mysql@sha256:c36050afdca850f23cef85703f84c7531a5ae155a11b5ee1c60acb09937c4084` | 8.4.9，已核实 amd64 |
| Redis | `docker.io/library/redis@sha256:6ab0b6e7381779332f97b8ca76193e45b0756f38d4c0dcda72dbb3c32061ab99` | 7.4.9，已核实 amd64 |

更新根声明或目标版本后，应在同一目标平台用固定生成器、经核实 wheel 集合和版本约束重新解析锁，再核对闭包与来源；不能只改根声明后沿用旧锁。当前基线保留 Poppler，apt 的 trixie/trixie-updates/trixie-security 来源及系统传递包未锁快照，重建时仍可能漂移。依赖版本/hash 与基础镜像身份固定不保证整镜像逐字节相同，也不代表真实 Word 客户端效果或生产验收通过。

## 环境变量

复制根目录样例并填入真实值：

```bash
cp .env.example .env
```

必须修改：

| 变量 | 说明 |
|---|---|
| `MD2WORD_IMAGE` | 生产 API/Worker 共用的版本化镜像引用，生产必填且无默认值；在当前 shell 导出或写入 `.env`。开发默认 `md2word-dev:local`，可用同名变量覆盖 |
| `MYSQL_ROOT_PASSWORD` | MySQL root 密码 |
| `JOBS_MYSQL_PASSWORD` | 应用 MySQL 用户密码 |
| `JOBS_ACCESS_TOKEN` | legacy jobs 接口 token |
| `ADMIN_TOKEN` | 运维接口 token |
| `AUTH_JWT_SECRET_KEY` | 内部账号 JWT 签名密钥 |
| `AUTH_INTERNAL_USERS_FILE` | 内部账号 JSON 文件路径，默认 `deploy/auth_internal_users.json` |
| `MINERU_API_TOKEN` | MinerU 在线解析 token |
| `MINERU_CALLBACK_URL` | MinerU 回调基础地址，例如 `https://md2word.962850.xyz/api/v1/mineru-callbacks/result` |
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
.venv/bin/python -c "from app.services.auth.service import hash_password; print(hash_password('change-me-password'))"
```

`deploy/auth_internal_users.json` 示例：

```json
{"users":[{"id":"operator-1","username":"operator","password_hash":"pbkdf2_sha256$260000$...","role":"operator","tenant_id":"default","company_id":"default","status":"active"}]}
```

`AUTH_INTERNAL_USERS_JSON` 仍保留为兼容入口，但不建议 Docker 部署使用。PBKDF2 hash 包含 `$`，放在 env 值里容易被 Compose 或 shell 转义；文件读取不会经过 shell 展开。

## 启动

以下命令用于另行授权的正式部署；B02 的隔离解析、定向测试和候选构建不包含服务启动。先准备上述 57 个 wheel，并选定本次唯一的镜像标签：

```bash
export MD2WORD_IMAGE="md2word-p0:${RELEASE_VERSION:?请设置本次发布版本}"
docker compose --env-file .env -f docker/prod/docker-compose.yml build api
docker compose --env-file .env -f docker/prod/docker-compose.yml up -d --no-build
```

在部署机上检查：

```bash
curl -sS http://127.0.0.1:${MD2WORD_API_BIND_PORT:-18000}/api/v1/health/live
curl -sS http://127.0.0.1:${MD2WORD_API_BIND_PORT:-18000}/api/v1/health/ready
touch /tmp/md2word_empty_env
docker run --rm --user 0 --network md2word-p0_default \
  -v "${RELEASE_DIR:-$PWD}:/app" \
  -v /tmp/md2word_empty_env:/app/.env:ro \
  -w /app "$MD2WORD_IMAGE" \
  python scripts/ops/check_release.py \
    --runtime-url http://md2word-p0-api-1:8000
GOLDEN_SAMPLE_USERNAME=admin GOLDEN_SAMPLE_PASSWORD='<admin-password>' \
  .venv/bin/python scripts/ops/check_release.py \
  --runtime-url http://127.0.0.1:${MD2WORD_API_BIND_PORT:-18000} \
  --golden-sample-preflight \
  --golden-sample-preflight-output tests/tmp/golden_sample_runs/preflight.json
docker compose --env-file .env -f docker/prod/docker-compose.yml ps
docker compose --env-file .env -f docker/prod/docker-compose.yml logs -f api worker
```

`check_release.py --runtime-url` 会读取 `/api/v1/health/ready`，同时检查 `deployment_init_ready`、`p0_document_jobs_ready`、MySQL metadata 和 Celery worker。公开或生产环境出现 `p0_document_jobs_blockers` 时，不应开放上传入口；常见阻断项是 document_jobs worker backend 未启用、Celery broker/queue 缺失、内部账号未配置、MinerU token/callback/uid 缺失。`--golden-sample-preflight` 只做快速门禁：4 个 canonical PDF、admin 登录角色和运行时 readiness，不提交真实转换任务。

停止：

```bash
docker compose --env-file .env -f docker/prod/docker-compose.yml down
```

如需同时删除 MySQL、Redis 和 artifact volume：

```bash
docker compose --env-file .env -f docker/prod/docker-compose.yml down -v
```

## 开发 Compose

需要专门在 Docker 环境里调完整依赖时，可以使用开发编排；同样需要先补齐 57 个 wheel。未设置 `MD2WORD_IMAGE` 时，开发 API/Worker 共用本地默认标签 `md2word-dev:local`；可在当前 shell 导出该变量或在 `.env` 中设置独立开发标签来覆盖，使用默认值时应确保两处没有遗留的生产镜像引用。当前 P0 发布验收不要求本地跑这一步，full-stack 证据以 hostdzire 为准：

```bash
docker compose --env-file .env -f docker/dev/docker-compose.yml build api
docker compose --env-file .env -f docker/dev/docker-compose.yml up -d --no-build
```

开发 API 的构建平台与 API/Worker 的运行平台均固定为 `linux/amd64`。Apple Silicon 通过 Docker 的 amd64 仿真使用同一锁，不新增 arm64 或多架构锁；需由本机 Docker 环境提供仿真支持。开发编排会把仓库挂载到容器 `/app`，API 使用 `uvicorn --reload`；生产编排则把代码复制进镜像。

## 已知边界

- 当前 compose 是单机 P0 部署，不包含 HTTPS、反向代理、对象存储生命周期规则和外部密钥系统。
- `AUTH_INTERNAL_USERS_FILE` 和 `AUTH_INTERNAL_USERS_JSON` 都为空时，`/api/v1/auth/login` 会返回 `auth_unconfigured`。
- `MINERU_API_TOKEN` 为空时，PDF 端到端解析不能完成。
- 管理员首次通过 `/settings/mineru` 保存账号与密钥后，运行时文件成为完整绑定的权威来源；只修改 `.env` 不会覆盖它。回滚到旧代码前应确认 `.env` 中仍有匹配的 token 与 UID。
- `MINERU_CALLBACK_URL` 为空时，MinerU 异步完成不会主动推回；document_jobs 可能停在 `running/parsing` 等待后续重投递或人工排查。
- `MINERU_UID` 为空且 callback payload 也不带 `uid` 时，ready health 会把 `mineru_uid_missing` 标为 blocker。
- 如改用 S3/OSS，需要把 `JOBS_ARTIFACT_STORAGE_BACKEND` 改为 `s3` 并补齐 bucket、endpoint、access key、secret 和下载模式。
