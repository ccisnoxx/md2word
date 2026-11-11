---
doc_type: dev-guide
slug: runbook
component: backend-runbook
status: current
summary: 当前后端本地开发、线上优先验证、运维动作和真实样例验证的运行说明。
tags: [backend, runbook, jobs, deploy, hostdzire]
last_reviewed: 2026-06-17
doc_status: active
last_verified_commit: null
owner: null
verification_scope: >-
  全文用途、原字段与现有入口/命令参数声明的局部静态核对；原历史结果和执行条件保留，未运行命令或重新验收。输入身份及旧说明差异见 ../../.trellis/tasks/11-10-documentation-evidence-governance/research/b3-preparation.md。
---

# 后端运行与线上验证说明

本页维护后端专项开发、运行与迁移程序；本批仅静态核对入口/参数声明，没有执行文中 API、服务启动、数据库迁移、发布检查或真实样例。原先分版本、环境与维护窗口的限制继续适用，具体核验边界见本文元数据所引本批证据。

## 0. 线上优先验证边界

当前 P0 验收以 [线上优先验证流程](../deploy/online-first-validation-workflow.md) 为准：本地只做代码/文档改写和不依赖真实服务的检查，完整 API、Worker、MySQL、Redis/Celery、MinerU 和 Golden Sample 证据在 `hostdzire` 收集。

B02 镜像构建以 [Docker 部署说明的依赖锁与构建输入](../deploy/p0-docker-deployment.md#依赖锁与构建输入) 为准。旧线上流程中的镜像构建/回滚命令仅适用于 B02 之前的版本，不构成新镜像的构建步骤；版本化镜像选择与回退边界见同一部署说明。

不要为了当前 P0 验收在本机启动前后端、MySQL、Redis/Celery、Worker 或前端 smoke。以下本地命令仅保留给专项开发调试使用，不构成本轮发布证据。

## 0.1 访问控制口径

当前 P0 主流程是 Files + Document Jobs，调用方先登录 `/api/v1/auth/login` 获取 Bearer JWT，再按 `operator` / `admin` 角色访问接口。普通 operator 可以上传、创建、查看、下载、取消、重试、归档自己的任务；任务级删除只允许 admin。

旧 Jobs HTTP、stage worker 和转换运行时已删除。`JOBS_ACCESS_MODE` 等既有配置与生产启动约束暂保留，但不提供旧 Jobs 执行入口；正式业务使用 Bearer JWT。部分配置与运维接口原有 `X-Admin-Token` 兼容合同保持。

## 0.2 环境配置样例

仓库根目录提供 `.env.example`，覆盖单实例生产化需要的主要配置：

- `JOBS_REPOSITORY_BACKEND=mysql` 与 `JOBS_MYSQL_*`
- `JOBS_ARTIFACT_STORAGE_BACKEND=local_file`，artifact 二进制仍保存在 artifact storage，不写入 MySQL
- `DOCUMENT_JOBS_WORKER_BACKEND=celery` 与 `DOCUMENT_JOBS_CELERY_*`
- `JOBS_ACCESS_MODE`、`JOBS_ACCESS_TOKEN`、`JOBS_OPS_ACCESS_MODE`、`ADMIN_TOKEN`
- `MINERU_CALLBACK_URL`、`MINERU_UID` 和 `MINERU_RESULT_HOST_ALLOWLIST`
- `LOG_FORMAT=json`
- `APP_VERSION` 和 `DEPLOYMENT_ID`，用于 P2 线上门禁和 health evidence 区分发布批次

`MINERU_CALLBACK_URL` 直接按官方 callback 地址填写；callback 验签依赖 `uid + seed + content`，不要再给 URL 追加自定义 token 或 query 参数。

不要把真实 token 或 password 提交到仓库；复制样例后在本地 `.env` 或部署环境里填真实值。

## 1. 本地服务启动（仅开发）

当前机器不作为 P0 full-stack 验证环境；只有在专项开发排查时才使用本节命令。

```bash
.venv/bin/python scripts/dev/run_api.py
```

默认监听：

```text
http://127.0.0.1:8000
```

## 2. 本地健康检查（仅开发）

```bash
curl http://127.0.0.1:8000/api/v1/health/live
curl http://127.0.0.1:8000/api/v1/health/ready
curl http://127.0.0.1:8000/api/v1/health/metrics
```

`ready` 里当前 worker/storage 口径应为：

- `worker_mode` 保留原配置回显；正式执行模式以 `document_jobs_worker_backend` 为准
- `configured_repository_backend=file`（默认；切换后可为 `database` 或 `mysql`）
- `effective_repository_backend=file`（默认；切换后可为 `database` 或 `mysql`）
- `artifact_storage=local_file`（默认；切换后可为 `local_object` 或 `s3`）

旧 stage spool 健康字段已移除；正式回调计数和 DocumentJob 超时/陈旧任务观察继续保留，启动恢复只处理正式任务。

`ready` 还会报告：

- `artifact_root_writable`
- `artifact_disk_free_bytes`
- `default_template_version`
- `default_term_rule_version`
- `default_translation_profile_version`
- `mysql_schema_bootstrap_available`
- `pdf_crop_tools_available`：`pdfinfo` 与 `pdftoppm`（Poppler，`poppler-utils`）是否都在 PATH 中。表格占位裁切、图片 PDF 回退和整页降级都依赖它们。缺失时报 `pdf_crop_tools_missing`：生产或 `single_tenant_public` 部署列为阻断项，且 `scripts/dev/run_document_worker.py` 拒绝启动；开发环境只告警，页面失败时无法恢复。`docker/prod`、`docker/dev` 镜像已内置；本地开发需自行安装（如 `brew install poppler`）。

`requirements.txt` 负责直接依赖声明；`tests/test_runtime_dependency_declarations.py` 要求 `app/` 的第三方导入都在其中直接声明或进入写明来源的白名单。镜像安装消费完整 hash 锁 `requirements/locks/cp311-linux-amd64.txt`，目标限定 CPython 3.11.18 / Debian 13 / linux/amd64；根声明变更须同步重新解析和核对锁，传递闭包不能代替直接声明。

dev/prod 构建均需在上下文的 `requirements/wheels/` 提供已对账官方 PyPI 文件与 SHA-256 的 57 个运行 wheel，不含 pip 工具；使用固定基础镜像自带的 pip 24.0 离线、hash 校验、仅 wheel 安装。`PyMySQL[rsa]` 保留既有 RSA 依赖能力，不表示已验证真实数据库 RSA 握手。API/Worker 共用 `MD2WORD_IMAGE`：生产必填，使用版本化标签并核对实际 image ID；开发默认 `md2word-dev:local`，可用同名变量覆盖，API 构建与 API/Worker 运行均固定 `linux/amd64`。制品来源清单、固定 Python/MySQL/Redis 引用及发布准备步骤见 [Docker 部署说明](../deploy/p0-docker-deployment.md#依赖锁与构建输入)。apt/Poppler 系统包仍可能漂移，锁与定向 DOCX 测试不代表整镜像字节可复现或生产验收。

`metrics` 是 JSON 运维计数，不是 Prometheus 格式；当前包括 `document_jobs` 状态计数、`document_job_callback_messages` 计数、资源版本计数和 audit event 总数；旧 `jobs`、`stage_messages` 字段仅保留为空对象，不读取旧仓储。

`ready` 和 `metrics` 都包含非敏感 `deployment` 对象：

- `environment`：当前 `APP_ENV`
- `public_deployment_mode`：当前 `PUBLIC_DEPLOYMENT_MODE`
- `version`：当前 `APP_VERSION`
- `deployment_id`：当前 `DEPLOYMENT_ID`，未设置时为 `null`
- `started_at`：API 进程启动时间

P2 内部单租户发布时，推荐在 hostdzire `.env` 中显式设置 `APP_VERSION` 和 `DEPLOYMENT_ID`，并用 `scripts/ops/run_p2_online_gate.py` 生成线上证据报告。

## 2.0 Document Jobs worker 模式

P0 准生产/生产基线使用 MySQL metadata + Celery/Redis + 单 worker：

```env
JOBS_REPOSITORY_BACKEND=mysql
DOCUMENT_JOBS_WORKER_BACKEND=celery
DOCUMENT_JOBS_CELERY_BROKER_URL=redis://redis:6379/0
DOCUMENT_JOBS_CELERY_QUEUE=document-jobs
DOCUMENT_JOBS_TRANSLATION_BATCH_CELERY_QUEUE=document-translation-batches
```

启动 API 后另起 Document Jobs worker：

```bash
.venv/bin/python scripts/dev/run_document_worker.py
```

预期：

- `/health/ready` 返回 `effective_repository_backend=mysql`
- `/health/ready` 返回 `document_jobs_worker_backend=celery`
- `/health/ready` 不出现 `document_jobs_metadata_store_not_mysql` 或 `document_jobs_worker_backend_eager_in_production`
- `/health/ready` 不出现 `document_jobs_celery_broker_url_missing`、`document_jobs_celery_queue_missing` 或 `document_jobs_translation_batch_celery_queue_missing`
- 生产部署默认保持单 worker，但该 worker 必须同时订阅 `document-jobs` 和 `document-translation-batches`，否则 P1 翻译任务会在 `ir_converting` 阶段留下 queued batch；多 worker 原子并发语义不是当前 P0 范围

## 2.1 旧链路移除与持久化边界

B05 第 3、4 步已移除旧 StageWorker、stage 调度/重放、Jobs 仓储与旧转换运行时，不能再启动旧 worker 或运行旧 metadata/artifact shadow 工具。

`JOBS_REPOSITORY_BACKEND` 继续选择正式 metadata adapter：本地可用 `file` 或 SQLite `database`，正式生产基线为 `mysql`。数据库保存正式任务、文件元数据、事件、回调、翻译批次和资源版本；产物字节由正式 `FileUploadService` 管理。

`jobs`、`job_files`、`stage_messages` 三张既有旧空表留待 B08 治理，本次只删除对应建表与仓储，不执行 DROP、不迁移旧任务。`job_events` 仍用于正式 DocumentJob 事件，全量保留建表与读写。

旧 file→SQLite/MySQL shadow copy 不适用于正式 DocumentJob，不再提供该命令。正式数据迁移需遵循具体迁移合同；现有状态与列表投影工具如下。

### CON-103 Migration A

`scripts/ops/migrate_document_job_state.py` 补 DocumentJob 四个状态字段及对应 SQL 投影；SQL schema 阶段也补查询投影列，以便状态回填同步维护。它不能替代列表投影的完整一致性校验。JSON payload 是权威，缺键采用 `pending/unreviewed/internal_draft/{}`，旧 QA 原文保留，不自动映射历史批准。执行前须暂停相关 API/Worker 写者；默认 dry-run/verify 不触发 bootstrap/DDL。按 `schema`、`backfill`、`all` 分阶段 apply，并使用报告中的 `last_successful_job_id` 续跑；MySQL DDL 部分成功时保留已加列、修复后前滚，不执行 DROP。真实 MySQL/InnoDB 与部署文件系统验证按具体版本、环境及对应执行证据判断；状态回填不能替代v2双表全量校验。

### DocumentJob 列表查询投影

当前代码的v2列表使用任务 `list_query_json`（存储版本3）和文件 `review_query_json`（存储版本2），只在JSON中保留小字段事实。完整规范文本存于job的 `list_descriptor_key/list_receipt_key/list_table_snapshot_key` 及file的 `review_descriptor_key/review_receipt_key`；SQLite TEXT/MySQL LONGTEXT，NULL表示未回填，合法不适用值为空串。有效复核按单次查询时刻计算。新writer同行维护事实，但schema bootstrap不重写历史数据；缺失或不兼容投影会明确失败，GET不回填或全量降级；陈旧事实由全量verify和查询差分阻断切换。详细合同见[任务列表有效复核v2](../../.trellis/spec/backend/document-job-list-query-v2.md)。

显式拆列入口为 `scripts/ops/migrate_document_job_list_keys.py`，与原 `scripts/ops/migrate_document_job_list_query.py` 共用当前回填实现，仅处理SQLite/MySQL。旧文件名入口也会写入新布局，不能用它作为旧版回退工具。以下是另行授权维护窗口内的操作程序，不表示本文触发任何数据库操作，也不允许复用未核对的连接配置。

```bash
# 默认只读预检；目标和授权确认前禁止改为apply。
.venv/bin/python scripts/ops/migrate_document_job_list_keys.py --backend mysql --dry-run --batch-size 100
```

工具不读取.env，MySQL目标必须通过明确的 `JOBS_MYSQL_HOST/PORT/USER/PASSWORD/DATABASE` 提供；入口本身不绑定服务器UUID，执行前须独立核对实例、库与授权窗口。SQLite可指定 `--backend database --database-path <metadata.sqlite3>`。dry-run/apply报告按 `tables.document_files` 和 `tables.document_jobs` 分开记录计数及游标；SQLite未完成日志的恢复或checkpoint属于另行授权的维护步骤，预检不会代做。 dry-run每表只扫描一批，继续全量预检使用各表的 `last_scanned_*`；apply在文件表仍有后续批次时不处理任务表，只能用已提交的 `last_successful_*` 续跑。两种模式退出0均不表示全量就绪，只有空游标verify成功并 `all_ready=true` 才表示完整一致。

1. 停止全部job/file写者，包括API、Worker、回调、清理和相关旁路；核对目标后完成整个库及对象/配置卷备份，并在独立隔离目标恢复核验。业务数据覆盖恢复与代码回滚分别授权。
2. 在同一目标完成两表全量dry-run，处理报告中的缺时间键、非法payload及投影构造错误；不得用动态默认now修补。部分质量、绑定和descriptor条件错误保存为投影标志，并非dry-run报告错误；后续按实际可达性执行旧/新查询差分，任一侧报错都阻断切换。apply先补所需列、回填文件事实，再回填任务事实；只改派生列，保留raw、未知字段、原时间及其他业务列。
3. apply只在整批提交后推进各表 `last_successful_file_id` / `last_successful_job_id`。需要续跑时使用对应 `--after-file-id` / `--after-job-id`；失败保留上个成功游标，不能跳过失败记录。MySQL新增列可能已隐式提交，不能声称DDL与批次共同回滚。
4. 停写持续到验收完成。`--verify`禁止任何非空游标，须从头在同一只读快照全量校验两表；不能按 `last_scanned_*` 分页续跑verify。两表错误/差异均为0且原列保真后，还须完成固定旧/新实现查询差分：两侧均无错误且结果相等，双方相同报错也不能通过。全部通过后再启动新API/Worker并完成正常用户验收。
5. 不支持旧writer与新查询滚动混写。拆列后的代码回退须保持停写，使用冻结升级前版本的回填工具从权威payload重建旧版本2/1大JSON并全量verify，之后才可恢复旧API/Worker；新增列可保留，不执行DROP。代码回滚还须保留原锁序、账本和结果凭据兼容下限；恢复旧writer写入后，再升级须重新停写并从空游标完整重建两表，不能只补NULL或沿用上次断点。遇阻塞或未知写结果立即停止，不自动覆盖恢复业务数据。

本地SQLite、fake MySQL及静态检查不替代真实MySQL 8.4语义与部署环境验证。只有对应版本的明确执行证据才能证明真实引擎、正式迁移或线上验收已完成；本地源码接回不触发新的线上发布。

## 2.2 正式文件存储与保留期

`FileUploadService` 继续按 `JOBS_ARTIFACT_STORAGE_BACKEND=local_file|local_object|s3` 管理正式文件。`local_file` 使用 `DATA_DIR/document_file_objects`，`local_object` 使用配置的对象目录，S3 使用现有 bucket/endpoint/凭据配置。下载依据文件记录中的 `object_key`，不重建历史路径。

旧 `JobFile` artifact adapter、shadow upload 和 `ArtifactRetentionPlanner` 已删除。正式保留期与物理清理由 Files API 的 preview、确认和审计合同负责；任务删除与文件清理是不同操作。

## 2.4 OpenAPI 快照与发布前检查

OpenAPI 快照保存在：

```text
docs/api/openapi.json
```

路由、schema、response model 或 endpoint 文档变更后，重新导出：

```bash
.venv/bin/python scripts/ops/export_openapi.py
```

发布前执行只读检查：

```bash
.venv/bin/python scripts/ops/check_release.py
```

预期 `Release check report` 顶层 `ok: True`。

hostdzire 准生产/生产环境还应带运行时和 Golden Sample 预检：

```bash
GOLDEN_SAMPLE_USERNAME=admin \
GOLDEN_SAMPLE_PASSWORD='<admin-password>' \
.venv/bin/python scripts/ops/check_release.py \
  --runtime-url http://127.0.0.1:${MD2WORD_API_BIND_PORT:-18000} \
  --golden-sample-preflight \
  --golden-sample-preflight-output tests/tmp/golden_sample_runs/preflight.json
```

当前 release check 包含：

- OpenAPI snapshot 一致性检查
- P0 health/ready、MySQL metadata、Celery worker 和 health/metrics targeted smoke
- P0 Word renderer/layout/table/formula 语义 targeted smoke
- Golden Sample manifest、DOCX quality evidence、admin sign-off validation targeted smoke
- Document Jobs admin delete 和 generated Word OOXML metadata smoke
- 正式共享模型合同测试
- JSON logging tests
- 可选 `--runtime-url` 真实 `/health/ready` 检查，要求 `deployment_init_ready=true`、`p0_document_jobs_ready=true`、`effective_repository_backend=mysql`、`document_jobs_worker_backend=celery`，且 `document_jobs_translation_batch_celery_queue` 已配置
- 可选 `--golden-sample-preflight`，只检查 4 个 canonical PDF、admin 登录角色和运行时门禁，不提交真实转换任务

如果 OpenAPI 分项失败，说明当前代码生成的 OpenAPI 与 `docs/api/openapi.json` 不一致；先确认 API 变更是否预期，再重新导出并提交快照。无 `--runtime-url` 的本地 release check 不访问真实 MinerU、OpenAI 或公网；带 `--runtime-url` 的运行时门禁应在 hostdzire 执行。

## 3. 本地 Document Job 调试（仅开发）

当前公开 P0 主链路是 Files + Document Jobs。Legacy `/api/v1/jobs` endpoint family 已从 v1 router 移除，只保留历史文档说明；新联调、前端和集成方不要再使用旧入口。

```bash
curl -sS -X POST "http://127.0.0.1:8000/api/v1/files/upload-url" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"filename":"source.pdf","mime_type":"application/pdf","size_bytes":12345,"file_type":"source_pdf"}'
```

按响应里的 `upload_url` 上传 PDF 内容后创建任务：

```bash
curl -sS -X POST "http://127.0.0.1:8000/api/v1/document-jobs" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"source_file_id":"{file_id}","mode":"direct_pdf_to_word","document_language":"auto"}'
```

查询任务和获取临时下载链接：

```bash
curl -sS "http://127.0.0.1:8000/api/v1/document-jobs/{job_id}" \
  -H "Authorization: Bearer ${TOKEN}"

curl -sS "http://127.0.0.1:8000/api/v1/document-jobs/{job_id}/download-url" \
  -H "Authorization: Bearer ${TOKEN}"
```

## 3.1 翻译 Provider 批次诊断

英译中 / 俄译中任务在 `ir_converting` 阶段会把 DocumentIR 文本拆成 provider batches。单任务诊断入口是内部工作台：

```text
/jobs/{job_id} -> 诊断 -> Provider 批次
```

也可以直接读取只读摘要接口：

```bash
curl -sS "http://127.0.0.1:8000/api/v1/document-jobs/{job_id}/translation-batches" \
  -H "Authorization: Bearer ${TOKEN}"
```

该接口只返回 batch 元数据、错误摘要和文件 ID，不返回完整 prompt、provider response、source text、translated text、debug archive 内容、对象存储定位或签名 URL。

常见判断口径：

| 现象 | Provider 批次信号 | 处理建议 |
|---|---|---|
| 正常成功 | 当前 leaf batches 均为 `succeeded`，任务 `status=succeeded`，结果文件存在。 | 可进入下载、QA 或验收复核。 |
| 截断自动恢复 | 父 batch 为 `split`，`finish_reason=length` 或 `truncation_retry=true`，子 batches 后续 `succeeded`。 | 这是预期恢复路径；记录 job id、batch id 和 AI call log file id 数量即可。 |
| 批次失败且重试耗尽 | batch 为 `failed`，`retryable=false`，`attempt_count=max_attempts`，`error_code/error_message` 有摘要。 | 使用任务级 `retry`，或把 job id、batch id、页范围、attempt、finish_reason 和 error 摘要交给开发排查。 |
| 批次仍在执行 | batch 为 `pending` / `queued` / `running`，任务仍在 `ir_converting`。 | 等待 bounded polling；若 `updated_at` 长时间不变，再检查 worker、Celery queue 和 lease 过期恢复。 |
| 疑似 fan-in 卡住 | 当前 leaf batches 均已 `succeeded`，但任务没有推进到渲染/结果保存。 | 记录全部 leaf batch id、generation、job retry_count、最近事件和 trace_id，升级开发排查 finalizer。 |
| 无 batch 记录 | 非翻译任务，或翻译任务尚未进入 provider batch 创建阶段。 | 先看任务 mode、stage、事件和 callback summary；不要把 direct PDF 任务视为异常。 |

排查时优先记录这些字段：

- `job_id`
- `generation`
- `batch_id`
- `root_batch_id` / `parent_batch_id`
- `status`
- `page_start` / `page_end`
- `item_count` / `char_count`
- `attempt_count` / `max_attempts`
- `finish_reason`
- `truncation_retry`
- `retryable`
- `provider_call_budget`
- `error_code` / `error_message`
- `ai_call_log_file_ids` 的数量或 ID 摘要

当前允许运维使用的动作仍是任务级动作：`retry`、`cancel`、`archive`、`unarchive`、`clone`、`download`，具体以任务详情返回的 `available_actions` 为准。当前没有批次级 `retry`、`cancel`、`requeue` 或强制 finalizer 写操作；不要通过数据库或队列手工改 batch 状态。

长 PDF 英译中上线验证应在 hostdzire 或等价 staging 执行。若使用私有 32 页失败样本或等价长 PDF，报告只记录样本标识、页数、job id、部署版本、batch 摘要和结果，不提交 PDF、全文、prompt、provider response、密钥或签名 URL。

## 3.2 历史 legacy jobs 入口

旧 `/api/v1/jobs` 和 `/api/v1/jobs/pdf` 入口已从公开 v1 API 移除，仅作为历史排查背景保留；不要用于新开发、联调或 P0 验收。历史链路曾支持 MinerU zip 上传、原始 PDF 在线提交、本地 callback 回放和旧 `download/result` 下载，但当前主合同统一使用 Files + Document Jobs：

- 上传和创建：`POST /api/v1/files/upload-url` -> `PUT /api/v1/files/{file_id}/content` -> `POST /api/v1/document-jobs`
- 查询：`GET /api/v1/document-jobs/{job_id}`
- 事件：`GET /api/v1/document-jobs/{job_id}/events`
- 文件：`GET /api/v1/document-jobs/{job_id}/files`
- 下载：`GET /api/v1/document-jobs/{job_id}/download-url`

MinerU callback 仍命中 `POST /api/v1/mineru-callbacks/result`，但任务观察和恢复证据读取 Document Jobs 详情、事件、文件和 callback summary，不再读取旧 jobs 详情页。

## 4.1 查询默认模板和配置元数据

```bash
curl "http://127.0.0.1:8000/api/v1/templates"
curl "http://127.0.0.1:8000/api/v1/templates/default"
curl -L "http://127.0.0.1:8000/api/v1/templates/default/download" -o template.docx
```

当前 `templates` 接口会返回：

- 默认 DOCX 模板元数据
- manifest 当前绑定的版式 YAML 元数据
- `subscripts_dictionary.yaml` 元数据
- API 上传模板的当前版本号

## 5. 本地运维动作

### retry

```bash
curl -sS -X POST "http://127.0.0.1:8000/api/v1/document-jobs/{job_id}/retry" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"reason":"rerun"}'
```

### cancel

```bash
curl -sS -X POST "http://127.0.0.1:8000/api/v1/document-jobs/{job_id}/cancel" \
  -H "Authorization: Bearer ${TOKEN}"
```

### archive / unarchive

```bash
curl -sS -X DELETE "http://127.0.0.1:8000/api/v1/document-jobs/{job_id}" \
  -H "Authorization: Bearer ${TOKEN}"

curl -sS -X POST "http://127.0.0.1:8000/api/v1/document-jobs/{job_id}/unarchive" \
  -H "Authorization: Bearer ${TOKEN}"
```

### admin delete

任务级删除只允许 admin 执行；operator 前端不展示入口，接口返回 `403 forbidden`。执行前必须先预览，再带 `reason`、确认短语和 `preview_hash` 提交。

```bash
curl -sS -X POST "http://127.0.0.1:8000/api/v1/document-jobs/{job_id}/delete-preview" \
  -H "Authorization: Bearer ${ADMIN_TOKEN}"

curl -sS -X POST "http://127.0.0.1:8000/api/v1/document-jobs/{job_id}/delete" \
  -H "Authorization: Bearer ${ADMIN_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"reason":"cleanup duplicate internal test","confirmation":"DELETE docjob_xxx","preview_hash":"<preview_hash>"}'
```

注意：

- 普通 operator 可以使用创建、查看、下载、取消、重试、归档等任务工作台动作，但不能执行任务级删除。
- Document Jobs replay / callback 诊断通过任务详情、事件、callback summary 和 Ops Dashboard 恢复动作处理，不再使用旧 jobs 运维端点。
- 文件物理清理仍走 Files retention 的 preview -> reason -> confirmation -> audit 流程；任务删除只清理可安全删除的关联本地文件，并保留任务 metadata、事件和 audit。

## 6. 真实样例联调口径

P0 Golden Sample 以 `tests/fixtures/golden_samples/pdfs` 下的四个 OPA228 datasheet 页为 canonical suite：

- `gs-003`: `OPA228_P1.pdf`
- `gs-004`: `OPA228_P2.pdf`
- `gs-006`: `OPA228_P6.pdf`
- `gs-008`: `OPA228_P7.pdf`

这四份样本通过 Files + Document Jobs 主链路执行 `direct_pdf_to_word`。P0 通过条件是 4/4 任务成功、4/4 结果 DOCX 可由 Word 打开、4/4 由 admin reviewer 人工签字通过；不再以扩充到 10-20 份样本作为阻塞条件。人工质量线要求接近原版排版并符合 Word 文档排版标准，二者冲突时以可维护的 Word 标准结构为准。

正式执行地点是 hostdzire；本地不跑真实 Golden Sample 转换。执行、签字和证据回填步骤见 [线上优先验证流程](../deploy/online-first-validation-workflow.md)。
