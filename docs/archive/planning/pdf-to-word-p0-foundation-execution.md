---
doc_type: implementation-note
slug: pdf-to-word-p0-foundation-execution
component: pdf-to-word-backend
status: current
summary: P0-001 至 P0-003 的执行记录，确认现有后端基线、公司环境连接参数清单和目标 MySQL 核心表结构草案。
tags: [implementation, p0, backend, mysql, config, pdf-to-word]
last_reviewed: 2026-05-29
---

# PDF 到模板化 Word 后端 P0 基础执行记录

## 1. 范围

本文完成 `pdf-to-word-implementation-checklist.md` 中 P0-001 至 P0-003：

| ID | 结论 |
|---|---|
| P0-001 | 已确认当前代码基线与目标架构差距，现有能力可复用但目标 P0 需要补 typed business schema、JWT、Celery/Redis 和 OSS 上传授权。 |
| P0-002 | 已列出公司开发环境连接参数清单，区分当前已接入配置与后续 P0 需要新增的配置。 |
| P0-003 | 已定义 MySQL 核心表结构草案，覆盖 `users`、`document_files`、`document_jobs`、`job_events`、模板相关表，并保留 `tenant_id`、`company_id`、`created_by`。 |

## 2. P0-001 当前代码基线与目标架构差距

### 2.1 可复用能力

| 能力 | 当前位置 | 复用方式 |
|---|---|---|
| FastAPI 后端组合根 | `app/main.py` | 继续作为 API service 入口，后续登录、文件、任务接口沿用同一 runtime 组装方式。 |
| Jobs 主链路 | `app/api/v1/routers/jobs*.py`, `app/services/jobs/` | 已有上传 MinerU zip、上传 PDF、任务查询、下载、重试、取消、callback 后处理能力，可作为 P0 document_jobs 的行为参考。 |
| MinerU 集成 | `app/clients/mineru_client.py`, `app/services/jobs/stage.py` | 已有在线提交、callback、主动恢复结果 zip 的 provider 边界，可继续复用。 |
| 转换链路 | `app/conversion/` | 已有 MinerU 结果包到 DOCX 的转换入口，P0 后续应逐步改为 MinerU -> DocumentIR -> Word。 |
| 模板能力 | `app/api/v1/routers/templates.py`, `app/services/templates/read_service.py` | 已有模板 CRUD、版本发布、默认版本、下载接口，可映射到目标 `word_templates` / `template_versions`。 |
| 术语和翻译配置版本 | `app/services/term_rules/`, `app/services/translation_profiles/`, `app/core/resource_models.py` | P1 翻译链路可复用资源版本模型；P0 仅需保留任务引用字段。 |
| Metadata backend seam | `app/repositories/protocols.py`, `file_job_repository.py`, `database_job_repository.py`, `mysql_job_repository.py` | 现有 protocol 和 MySQL adapter 可复用连接、测试和运行时切换经验。 |
| Artifact storage seam | `app/services/jobs/artifact_storage.py`, `object_artifact_storage.py` | 已支持 local、local_object、S3-compatible redirect/stream 下载；P0 OSS 文件元数据可沿用 object_key 语义。 |
| Health / readiness | `app/services/health_service.py` | 已暴露 metadata store、artifact storage、MinerU token 和 stage spool 可用性。 |
| 审计事件 | `app/core/audit_models.py`, repository `audit_events` | admin 写接口已具备审计基础，P0 登录、上传、建任务、下载授权可继续扩展。 |

### 2.2 目标架构差距

| 差距 | 当前状态 | P0 影响 | 后续任务 |
|---|---|---|---|
| 内部账号 + JWT | 当前是 `X-Jobs-Token` / `X-Admin-Token`，没有 `users`、密码哈希、JWT 登录态和 `admin/operator` 角色。 | 无法满足内部登录和 owner/admin 查询边界。 | P0-004 |
| Typed business schema | MySQL adapter 当前使用 `jobs`、`job_files`、`job_events` 等 JSON payload 表；目标计划需要 `document_jobs`、`document_files`、模板业务表。 | MySQL 可用但还不是 PRD 中的业务表权威模型。 | P0-006, P0-009, P0-010 |
| Celery + Redis | 当前 worker 是 `BackgroundTasks + stage message store`，也支持 `scripts/dev/run_stage_worker.py` 轮询；没有 Celery broker。 | P0 目标中的 Redis/Celery 投递、超时和重试还未落地。 | P0-013, P0-014 |
| OSS 上传授权 | 当前 artifact adapter 支持 S3-compatible 上传生成结果；没有 `/api/files/upload-url` 和独立 `document_files` 登记。 | 前端直传、上传前校验、文件过期策略无法闭环。 | P0-006, P0-007, P0-030 |
| PDF 业务校验 | 当前 `POST /api/v1/jobs/pdf` 校验扩展名、content-type、文件头和大小；未实现页数 200 限制。 | P0 文件校验还缺页数读取失败/超限错误。 | P0-008 |
| DocumentIR | 当前 conversion 主要消费 MinerU 输出包，尚无独立 DocumentIR v1 schema。 | 解析、翻译和 Word 渲染边界仍耦合。 | P0-017, P0-018 |
| 目标 API path | 当前 API 是 `/api/v1/jobs` / `/api/v1/jobs/pdf`；技术计划目标是 `/api/document-jobs` 等命名。 | 后续需要决定是兼容现有 jobs API，还是新增 document-jobs facade。 | P0-010, P0-011 |
| 迁移工具 | 当前无 Alembic；sqlite/MySQL schema 由 repository adapter 启动 bootstrap。 | typed MySQL 表落地前需确认是否继续 bootstrap，还是引入迁移工具。 | P0-003 后续决策 |

### 2.3 执行建议

- P0 后续不要推倒现有 jobs workflow；应先在现有 repository/service seam 上加 typed business model，再逐步替换 JSON payload 表。
- 目标 MySQL 业务表可以先作为新 schema 草案，实际实现时保留旧 `jobs` / `job_files` 表的迁移或兼容策略。
- Celery 接入前，当前 `stage_messages` 语义仍可作为幂等和恢复设计参考。

## 3. P0-002 公司开发环境连接参数清单

### 3.1 当前已接入配置

| 类别 | 配置项 | 当前状态 | 说明 |
|---|---|---|---|
| App | `APP_NAME`, `APP_ENV`, `LOG_FORMAT`, `APP_CORS_ORIGINS`, `DATA_DIR` | 已接入 | FastAPI runtime、日志和数据目录基础配置。 |
| MySQL metadata | `JOBS_REPOSITORY_BACKEND=mysql`, `JOBS_MYSQL_HOST`, `JOBS_MYSQL_PORT`, `JOBS_MYSQL_USER`, `JOBS_MYSQL_PASSWORD`, `JOBS_MYSQL_DATABASE`, `JOBS_MYSQL_CHARSET`, `JOBS_MYSQL_CONNECT_TIMEOUT_SECONDS` | 已接入 | 当前保存现有 jobs metadata JSON payload，不是本文件第 4 节的 typed business schema。 |
| Artifact / OSS-compatible | `JOBS_ARTIFACT_STORAGE_BACKEND`, `JOBS_ARTIFACT_S3_BUCKET`, `JOBS_ARTIFACT_S3_ENDPOINT_URL`, `JOBS_ARTIFACT_S3_REGION`, `JOBS_ARTIFACT_S3_ACCESS_KEY_ID`, `JOBS_ARTIFACT_S3_SECRET_ACCESS_KEY`, `JOBS_ARTIFACT_S3_KEY_PREFIX`, `JOBS_ARTIFACT_S3_PUBLIC_BASE_URL`, `JOBS_ARTIFACT_S3_DOWNLOAD_MODE`, `JOBS_ARTIFACT_S3_PRESIGN_EXPIRES_SECONDS` | 已接入 | 使用 S3-compatible API 表达公司 OSS；真实厂商字段需按公司 OSS SDK 或兼容层确认。 |
| Worker mode | `JOBS_WORKER_MODE`, `JOBS_WORKER_POLL_INTERVAL_SECONDS`, `JOBS_WORKER_ID`, `STAGE_MESSAGE_LEASE_SECONDS` | 已接入 | 当前 in-process / external polling worker 配置，尚不是 Celery。 |
| 临时 token 鉴权 | `JOBS_ACCESS_MODE`, `JOBS_ACCESS_TOKEN`, `JOBS_OPS_ACCESS_MODE`, `ADMIN_TOKEN` | 已接入 | 当前访问控制，不等同于 P0-004 的用户登录 + JWT。 |
| 上传限制 | `JOBS_UPLOAD_MAX_BYTES` | 已接入 | 当前默认 50MB；页数限制需要 P0-008 补齐。 |
| MinerU | `MINERU_API_TOKEN`, `MINERU_MODEL_VERSION`, `MINERU_LANGUAGE`, `MINERU_ENABLE_FORMULA`, `MINERU_ENABLE_TABLE`, `MINERU_CALLBACK_URL`, `MINERU_UID`, `MINERU_CALLBACK_TOKEN`, `MINERU_CALLBACK_TOKEN_QUERY_NAME`, `MINERU_RESULT_HOST_ALLOWLIST` | 已接入 | 支持 PDF 在线提交、callback 鉴权和结果 URL allowlist。 |
| 模板 / 术语 / 翻译 | `DEFAULT_TEMPLATE_ID`, `TEMPLATES_MANIFEST_PATH`, `TEMPLATES_STORAGE_PATH`, `TEMPLATE_STATE_PATH`, `TERM_RULES_*`, `OPENAI_*`, `TRANSLATION_*` | 已接入 | P0 模板和 P1 翻译相关配置已有基础。 |

### 3.2 P0 后续需要新增或确认的配置

| 类别 | 建议配置项 | 是否已有代码消费 | 建议默认值 | 用途 |
|---|---|---:|---|---|
| Redis / Celery | `CELERY_BROKER_URL` | 否 | `redis://127.0.0.1:6379/0` | Celery broker。 |
| Redis / Celery | `CELERY_RESULT_BACKEND` | 否 | 空或 `redis://127.0.0.1:6379/1` | P0 可不依赖 Celery result backend，任务状态以 MySQL 为准。 |
| Redis / Celery | `CELERY_TASK_DEFAULT_QUEUE` | 否 | `pdf-to-word` | P0 Worker 队列名。 |
| Redis / Celery | `CELERY_WORKER_CONCURRENCY` | 否 | `2` | 单机 Worker 并发控制。 |
| 超时 | `P0_DOCUMENT_JOB_TIMEOUT_SECONDS` | 否 | `1200` | P0 20 分钟任务超时。 |
| JWT | `AUTH_JWT_SECRET_KEY` | 否 | 无，必须部署注入 | JWT 签名密钥，不能提交真实值。 |
| JWT | `AUTH_JWT_ALGORITHM` | 否 | `HS256` | JWT 签名算法。 |
| JWT | `AUTH_ACCESS_TOKEN_EXPIRE_MINUTES` | 否 | `120` | 内部用户登录 token 过期时间。 |
| 密码哈希 | `AUTH_PASSWORD_HASH_SCHEME` | 否 | `bcrypt` | P0 内部账号密码哈希策略。 |
| OSS 上传授权 | `OSS_UPLOAD_PRESIGN_EXPIRES_SECONDS` | 否 | `600` | 上传授权有效期。 |
| OSS 上传限制 | `OSS_UPLOAD_MAX_BYTES` | 否 | `52428800` | 与 `JOBS_UPLOAD_MAX_BYTES` 对齐。 |
| OSS 上传限制 | `OSS_UPLOAD_ALLOWED_MIME_TYPES` | 否 | `application/pdf` | 上传入口允许类型。 |
| OSS 生命周期 | `DOCUMENT_FILE_RETENTION_DAYS` | 否 | `90` | 原始 PDF、中间文件和 Word 默认保留期。 |

### 3.3 公司环境待确认项

| 问题 | 影响任务 | 建议确认对象 |
|---|---|---|
| MySQL 版本是否支持 `JSON` 类型和 `CHECK` 约束 | P0-003, P0-006, P0-009 | DBA / 运维 |
| MySQL schema 变更用 adapter bootstrap、SQL 文件，还是 Alembic | P0-003 后续实现 | 后端负责人 / DBA |
| Redis 地址、库编号、认证、最大连接数和持久化策略 | P0-013 | 运维 |
| 公司 OSS 是否完全兼容 S3 API，或需要厂商 SDK | P0-007, P0-025 | 云资源负责人 |
| OSS bucket、endpoint、region、key prefix、上传/下载签名规则 | P0-007, P0-025 | 云资源负责人 |
| JWT 密钥注入方式和轮换策略 | P0-004 | 运维 / 安全 |
| MinerU 调用方式是当前 HTTP API、容器、还是公司内网服务 | P0-015 | 平台 / 算法负责人 |

## 4. P0-003 MySQL 核心表结构草案

### 4.1 设计约束

- 以 MySQL 存业务 metadata，PDF、图片、MinerU 原始结果、DocumentIR 和 Word 二进制只存 OSS 引用。
- P0 保留单租户简化，但所有核心业务表保留 `tenant_id`、`company_id`、`created_by`。
- 状态和阶段先用字符串字段，不引入 lookup 表，避免 P0 过度建模。
- `payload`、`quality_flags`、`metadata` 等字段优先使用 MySQL `JSON`；如公司 MySQL 版本不支持，落地时改为 `LONGTEXT` 并由应用层校验。
- 本节是业务表草案，不要求直接替换当前 `MysqlJobRepository` 的 JSON payload bootstrap 表。

### 4.2 支撑表

```sql
CREATE TABLE tenants (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(128) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    created_at DATETIME(6) NOT NULL,
    updated_at DATETIME(6) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE companies (
    id VARCHAR(64) PRIMARY KEY,
    tenant_id VARCHAR(64) NOT NULL,
    name VARCHAR(128) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    created_at DATETIME(6) NOT NULL,
    updated_at DATETIME(6) NOT NULL,
    KEY idx_companies_tenant_status (tenant_id, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### 4.3 用户表

```sql
CREATE TABLE users (
    id VARCHAR(64) PRIMARY KEY,
    tenant_id VARCHAR(64) NOT NULL,
    company_id VARCHAR(64) NOT NULL,
    username VARCHAR(128) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(32) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    display_name VARCHAR(128) NULL,
    last_login_at DATETIME(6) NULL,
    created_by VARCHAR(64) NULL,
    created_at DATETIME(6) NOT NULL,
    updated_at DATETIME(6) NOT NULL,
    UNIQUE KEY uq_users_tenant_username (tenant_id, username),
    KEY idx_users_company_status (company_id, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

P0 约束：

- `role` 只允许 `admin`、`operator`。
- `status` 只允许 `active`、`disabled`。
- `password_hash` 不保存明文密码；初始管理员可由种子脚本或后台运维创建。

### 4.4 文件元数据表

```sql
CREATE TABLE document_files (
    id VARCHAR(64) PRIMARY KEY,
    tenant_id VARCHAR(64) NOT NULL,
    company_id VARCHAR(64) NOT NULL,
    job_id VARCHAR(64) NULL,
    file_type VARCHAR(64) NOT NULL,
    storage_provider VARCHAR(32) NOT NULL,
    bucket VARCHAR(128) NOT NULL,
    object_key VARCHAR(512) NOT NULL,
    original_filename VARCHAR(255) NULL,
    mime_type VARCHAR(128) NOT NULL,
    size_bytes BIGINT UNSIGNED NOT NULL,
    checksum_sha256 VARCHAR(80) NULL,
    etag VARCHAR(128) NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    expires_at DATETIME(6) NULL,
    metadata JSON NULL,
    created_by VARCHAR(64) NOT NULL,
    created_at DATETIME(6) NOT NULL,
    updated_at DATETIME(6) NOT NULL,
    UNIQUE KEY uq_document_files_object (bucket, object_key),
    KEY idx_document_files_job_type (job_id, file_type),
    KEY idx_document_files_owner (tenant_id, company_id, created_by),
    KEY idx_document_files_expires_at (expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

P0 文件类型建议：

- `source_pdf`
- `mineru_raw_result`
- `document_ir`
- `image_asset`
- `generated_word`
- `template_docx`
- `template_config`
- `term_file`

### 4.5 模板表

```sql
CREATE TABLE word_templates (
    id VARCHAR(64) PRIMARY KEY,
    tenant_id VARCHAR(64) NOT NULL,
    company_id VARCHAR(64) NOT NULL,
    name VARCHAR(128) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'draft',
    description VARCHAR(512) NULL,
    created_by VARCHAR(64) NOT NULL,
    created_at DATETIME(6) NOT NULL,
    updated_at DATETIME(6) NOT NULL,
    UNIQUE KEY uq_word_templates_company_name (company_id, name),
    KEY idx_word_templates_tenant_status (tenant_id, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE template_versions (
    id VARCHAR(64) PRIMARY KEY,
    tenant_id VARCHAR(64) NOT NULL,
    company_id VARCHAR(64) NOT NULL,
    template_id VARCHAR(64) NOT NULL,
    version VARCHAR(64) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'draft',
    docx_sample_file_id VARCHAR(64) NOT NULL,
    config_file_id VARCHAR(64) NULL,
    rule_version VARCHAR(64) NULL,
    snapshot_hash VARCHAR(128) NOT NULL,
    published_at DATETIME(6) NULL,
    created_by VARCHAR(64) NOT NULL,
    created_at DATETIME(6) NOT NULL,
    updated_at DATETIME(6) NOT NULL,
    UNIQUE KEY uq_template_versions_template_version (template_id, version),
    KEY idx_template_versions_status (tenant_id, company_id, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

P0 约束：

- `word_templates.status` 建议为 `draft`、`published`、`disabled`。
- `template_versions.status` 建议为 `draft`、`published`、`disabled`、`superseded`。
- P0 可先通过种子数据或后台脚本注册 1-2 套模板，在线编辑器后置。

### 4.6 文档任务表

```sql
CREATE TABLE document_jobs (
    id VARCHAR(64) PRIMARY KEY,
    tenant_id VARCHAR(64) NOT NULL,
    company_id VARCHAR(64) NOT NULL,
    created_by VARCHAR(64) NOT NULL,
    source_file_id VARCHAR(64) NOT NULL,
    mode VARCHAR(32) NOT NULL,
    document_language VARCHAR(16) NOT NULL DEFAULT 'auto',
    status VARCHAR(32) NOT NULL,
    stage VARCHAR(64) NOT NULL,
    progress TINYINT UNSIGNED NOT NULL DEFAULT 0,
    template_version_id VARCHAR(64) NOT NULL,
    term_version_id VARCHAR(64) NULL,
    result_file_id VARCHAR(64) NULL,
    mineru_batch_id VARCHAR(128) NULL,
    mineru_data_id VARCHAR(128) NULL,
    failed_stage VARCHAR(64) NULL,
    error_code VARCHAR(64) NULL,
    error_message VARCHAR(1024) NULL,
    retry_count INT UNSIGNED NOT NULL DEFAULT 0,
    timeout_at DATETIME(6) NULL,
    started_at DATETIME(6) NULL,
    completed_at DATETIME(6) NULL,
    canceled_at DATETIME(6) NULL,
    request_snapshot JSON NULL,
    created_at DATETIME(6) NOT NULL,
    updated_at DATETIME(6) NOT NULL,
    KEY idx_document_jobs_owner_created (tenant_id, company_id, created_by, created_at),
    KEY idx_document_jobs_status_stage (status, stage, created_at),
    KEY idx_document_jobs_source_file (source_file_id),
    KEY idx_document_jobs_template_version (template_version_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

P0 状态建议：

| 字段 | 取值 |
|---|---|
| `mode` | `direct_pdf_to_word`, `en2zh_pdf_to_word` |
| `status` | `pending`, `queued`, `running`, `succeeded`, `failed`, `canceled` |
| `stage` | `uploaded`, `parsing`, `parsed`, `ir_converting`, `rendering`, `uploading`, `completed`, `failed`, `canceled` |

说明：

- P0 中文主链路只使用 `direct_pdf_to_word`；`en2zh_pdf_to_word` 为 P1 预留。
- `document_jobs` 是任务状态权威来源；Celery result backend 不作为查询真相来源。
- `request_snapshot` 保存创建任务时绑定的模板、MinerU 非敏感配置、文件摘要等快照，不保存完整 PDF 文本。

### 4.7 任务事件表

```sql
CREATE TABLE job_events (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    tenant_id VARCHAR(64) NOT NULL,
    company_id VARCHAR(64) NOT NULL,
    job_id VARCHAR(64) NOT NULL,
    created_by VARCHAR(64) NOT NULL,
    stage VARCHAR(64) NOT NULL,
    level VARCHAR(16) NOT NULL,
    event_type VARCHAR(64) NOT NULL,
    message VARCHAR(512) NOT NULL,
    payload JSON NULL,
    duration_ms INT UNSIGNED NULL,
    trace_id VARCHAR(128) NULL,
    created_at DATETIME(6) NOT NULL,
    KEY idx_job_events_job_id_id (job_id, id),
    KEY idx_job_events_owner_created (tenant_id, company_id, created_by, created_at),
    KEY idx_job_events_stage_level (stage, level, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

P0 约束：

- `level` 建议为 `info`、`warning`、`error`。
- `event_type` 建议覆盖 `stage_started`、`stage_succeeded`、`stage_failed`、`file_registered`、`retry_requested`、`download_authorized`。
- `payload` 不默认写 PDF 原文、完整翻译文本、密钥、签名 URL 或本地绝对路径。

## 5. 与当前代码的映射

| 目标表 | 当前近似能力 | 落地建议 |
|---|---|---|
| `users` | `ADMIN_TOKEN` / `JOBS_ACCESS_TOKEN` | P0-004 新增用户模型、登录 service 和 JWT dependency；保留 token 模式作为本地/运维兼容。 |
| `document_files` | `JobFile`, `job_files`, artifact storage adapter | P0-006 把 `JobFile` 扩展或新增文件元数据模型，保留 `object_key` 和 checksum。 |
| `document_jobs` | `JobRecord`, `jobs` | P0-009/P0-010 明确定义 typed job status/stage 后再实现。 |
| `job_events` | `JobEvent`, `job_events` | P0-012 可沿用 append/list 接口，补 level、duration、owner 字段。 |
| `word_templates` / `template_versions` | template manifest + runtime state + resource versions | P0-021 可先做只读注册或种子同步，不必立即重写现有模板 API。 |

## 6. 验收记录

| ID | 验收标准 | 本次结果 |
|---|---|---|
| P0-001 | 明确哪些现有能力可复用，哪些需要新增或改造 | 已完成，见第 2 节。 |
| P0-002 | MySQL、Redis、OSS、JWT 密钥、MinerU 配置项列清楚 | 已完成，见第 3 节。 |
| P0-003 | 覆盖 P0 必需字段，并保留 `tenant_id`、`company_id`、`created_by` | 已完成，见第 4 节。 |
