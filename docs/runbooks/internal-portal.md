---
doc_type: runbook
slug: internal-portal
component: md2word-internal-portal
status: current
summary: md2word 正式公司内部门户的产品边界、角色、页面/API 地图、部署配置和账号运营说明。
tags: [internal-portal, frontend, backend, auth, deploy, operations]
last_reviewed: 2026-06-10
---

# md2word 正式内部门户运行说明

## 1. 产品边界

md2word 第一阶段是公司内部文档转换和配置治理门户，不是外部客户自助站点。系统服务内部文档交付、翻译 QA、配置治理和技术运营人员，主链路是：

```text
files 上传授权 -> document_jobs 创建任务 -> Worker 调用 MinerU/DocumentIR/renderer -> Word 结果下载
```

当前明确不做：

- 外部客户门户、多租户自助控制台和计费。
- 公司 SSO 接入；第一版继续使用内部账号文件 + JWT。
- 在线 Word 编辑、在线人工改译文后重新生成 Word。
- 任务级真实删除文件；文件删除只走文件管理与清理工作区的 retention/preview/confirmation/audit 合同。
- 真实 S3 删除、自动清理执行和 provider cancellation 默认仍保持 gated/deferred。

## 2. 内部角色

| 角色 | 前端入口 | 能做什么 | 不应做什么 |
| --- | --- | --- | --- |
| `operator` | 任务工作台、翻译 QA、术语建议 | 上传 PDF、创建任务、查看进度、下载结果、提交术语建议、复核翻译证据 | 进入配置中心、系统状态、审计日志、文件清理 |
| `admin` | 全部内部入口 | 配置模板/术语/翻译版本、审核提案、查看审计、处理文件容量与清理、查看运维状态 | 绕过 preview/reason/confirmation 执行危险操作 |

账号字段保留 `tenant_id` 和 `company_id`，但第一版按单租户内部系统使用，不实现复杂租户隔离。

## 3. 页面地图

| 页面 | 受众 | 用途 |
| --- | --- | --- |
| `/login` | 全员 | 内部账号登录，获取 JWT。 |
| `/jobs` | operator/admin | 筛选任务、批量处理、下载、重试、取消、归档、clone/rerun。 |
| `/jobs/new` | operator/admin | 上传 PDF 并创建转换任务。 |
| `/jobs/:jobId` | operator/admin | 查看任务详情、文件、事件、失败信息、配置快照和可用操作。 |
| `/translation-qa` | operator/admin | 翻译 QA 队列，筛选未复核或有问题的英译中任务。 |
| `/jobs/:jobId/translation-qa` | operator/admin | 单任务翻译证据复核和术语建议跳转。 |
| `/term-proposals` | operator/admin | operator 提交建议；admin 审核提案。 |
| `/settings` | admin | 配置中心首页，按治理域进入模板、术语、翻译配置。 |
| `/settings/templates` | admin | 模板配置和版本治理。 |
| `/settings/term-rule-sets` | admin | 术语工作台：草稿与发布。 |
| `/settings/term-rules` | admin | 术语工作台：当前生效规则检查和模拟。 |
| `/settings/translation-profiles` | admin | 翻译配置版本治理。 |
| `/settings/translation-term-sets` | admin | 翻译术语集导入、diff、preflight、发布和回滚。 |
| `/system-status` | admin | 只读系统状态概览。 |
| `/system-status/ops-dashboard` | admin | 运维 readiness、受控真实集成 gate 和恢复动作预览。 |
| `/system-status/audit-events` | admin | 审计日志查询和导出。 |
| `/system-status/file-retention` | admin | 文件库、容量与策略、清理执行三段式文件管理工作区。 |

## 4. API 域

| API 域 | 当前职责 |
| --- | --- |
| `/api/v1/auth` | 内部账号登录和当前用户查询。 |
| `/api/v1/files` | 上传授权、文件内容上传、文件库搜索、quota、retention、cleanup run。 |
| `/api/v1/document-jobs` | PDF -> Word 主任务创建、查询、事件、文件、QA、retry/cancel/archive/unarchive/clone/download。 |
| `/api/v1/templates` | 模板详情、版本创建、发布、设默认和禁用。 |
| `/api/v1/term-rule-sets` | 术语规则集 draft、diff、preflight、publish、default、rollback。 |
| `/api/v1/term-rules` | 当前 live 术语规则检查、模拟和兼容入口。 |
| `/api/v1/translation-profiles` | 翻译配置版本治理。 |
| `/api/v1/translation-term-sets` | 翻译术语集版本治理。 |
| `/api/v1/*-proposals` | 术语规则和翻译术语建议审核。 |
| `/api/v1/audit-events` | 审计日志。 |
| `/api/v1/ops` | 真实集成控制面和运维动作预览。 |
| `/api/v1/health` | live/ready/metrics 观测。 |

OpenAPI 快照在 [docs/api/openapi.json](/Users/sc/PycharmProjects/md2word/docs/api/openapi.json)，API 文档入口在 [docs/api/manifest.yaml](/Users/sc/PycharmProjects/md2word/docs/api/manifest.yaml)。

## 5. 正式部署配置

正式内部门户推荐使用 Docker P0 编排，详见 [P0 Docker 部署说明](/Users/sc/PycharmProjects/md2word/docs/deploy/p0-docker-deployment.md)。

关键环境变量建议：

```env
APP_ENV=prod
LOG_FORMAT=json
JOBS_REPOSITORY_BACKEND=mysql
JOBS_ARTIFACT_STORAGE_BACKEND=local_object
DOCUMENT_JOBS_WORKER_BACKEND=celery
JOBS_ACCESS_MODE=token
JOBS_OPS_ACCESS_MODE=admin
AUTH_INTERNAL_USERS_FILE=deploy/auth_internal_users.json
AUTH_JWT_SECRET_KEY=<strong-random-secret>
MINERU_API_TOKEN=<mineru-token>
MINERU_CALLBACK_URL=https://<internal-domain>/api/v1/mineru-callbacks/result
MINERU_UID=<mineru-uid>
```

部署检查：

```bash
docker compose --env-file .env -f docker/prod/docker-compose.yml up -d --build
curl -sS http://127.0.0.1:${MD2WORD_API_BIND_PORT:-18000}/api/v1/health/live
curl -sS http://127.0.0.1:${MD2WORD_API_BIND_PORT:-18000}/api/v1/health/ready
curl -sS http://127.0.0.1:${MD2WORD_API_BIND_PORT:-18000}/api/v1/health/metrics
```

发布前检查：

```bash
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/check_release.py
cd frontend && npm run build
```

## 6. 账号运营

内部账号从 `AUTH_INTERNAL_USERS_FILE` 读取，推荐文件为 `deploy/auth_internal_users.json`。不要把真实文件提交到仓库；`.gitignore` 已排除该路径。

账号示例：

```json
{
  "users": [
    {
      "id": "operator-1",
      "username": "operator",
      "password_hash": "pbkdf2_sha256$260000$...",
      "role": "operator",
      "tenant_id": "default",
      "company_id": "default",
      "status": "active",
      "display_name": "交付人员"
    }
  ]
}
```

生成密码 hash：

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -c "from app.services.auth.service import hash_password; print(hash_password('change-me-password'))"
```

账号操作原则：

- 新增人员：追加用户记录，设置 `status=active`，重启 API/worker 使配置生效。
- 禁用人员：把 `status` 改为 `disabled`，重启 API/worker；已有 JWT 在后端校验时会因账号不可用而失效。
- 角色调整：只使用 `operator` 和 `admin` 两类角色；新增角色需要先设计权限合同。
- 密钥轮换：更换 `AUTH_JWT_SECRET_KEY` 会使现有 token 全部失效，需通知用户重新登录。

## 7. 数据与文件边界

- MySQL 只保存 metadata：任务、文件记录、事件、审计、资源版本等。
- PDF、Word、MinerU raw result、DocumentIR 和 AI debug artifact 不写入 MySQL，受 `JOBS_ARTIFACT_STORAGE_BACKEND` 控制。
- 文件管理与清理工作区只按 metadata 和 exact file ids 操作；物理删除必须经过 preview、reason、confirmation 和 audit。
- 系统状态页不承载危险操作，危险清理入口只在 `/system-status/file-retention` 的“清理执行”视图里。
- debug archive 可能包含全文证据，默认短保留期；生产启用前要确认 `TRANSLATION_DEBUG_ARCHIVE_ENABLED` 和保留天数。

## 8. 验收清单

- operator 可以登录、上传 PDF、创建任务、查看进度、下载结果、进入翻译 QA、提交术语建议。
- operator 访问 `/settings/**`、`/system-status/**` 会被前端路由拦回任务工作台，后端 admin API 仍有权限校验。
- admin 可以进入配置中心、系统状态、审计日志、文件管理与清理。
- 文件清理必须保持 preview -> reason -> confirmation -> audit，不新增任务级一键删除。
- `/health/ready` 不应出现未解释的 blocker；如有 MinerU、worker、MySQL、artifact storage blocker，先处理再开放使用。
- `scripts/ops/check_release.py` 和 `frontend npm run build` 通过后再发布。
