---
doc_type: requirement
slug: fastapi-backend-productization
pitch: 把 MinerU 结果转 DOCX 的能力产品化为可调用、可观察、可运维的 FastAPI 后端
status: current
last_reviewed: 2026-06-03
implemented_by:
  - fastapi-backend
tags: [backend, fastapi, jobs, docx]
---

# FastAPI 后端产品化

## 用户故事

- 作为前端或脚本调用方，我希望上传一个 MinerU 输出 zip 后，通过稳定的 HTTP API 获得任务状态和最终 DOCX，而不是只能手动跑本地脚本。
- 作为需要联调翻译能力的人，我希望同一条任务链路支持 `direct` 和 `en2zh`，并在翻译不可用时提前得到明确错误。
- 作为维护者，我希望通过 `health`、任务事件和本地运维动作判断任务卡在哪一步，并在必要时执行 retry、cancel 或 cleanup。
- 作为集成方，我希望读取默认模板和绑定 YAML 配置的元数据，确认当前服务到底使用哪套模板和版式约束。
- 作为模板维护者，我希望通过 API 管理 Template Profile 的 DOCX、layout 和 render_policy 版本，发布后再设默认或禁用旧版本，而不是直接覆盖线上模板文件。
- 作为术语维护者，我希望先编辑 Term Rule Set 草稿，再发布为不可变版本并设为默认或回滚，而不是直接覆盖当前任务使用的 runtime YAML。
- 作为翻译配置维护者，我希望先编辑 Translation Profile 草稿，再发布为不可变版本并设为默认或回滚，同时能在 job 产物中看到 segment 级 AI 初译和最终渲染文本。
- 作为维护者和集成方，我希望任务创建时锁定实际使用的模板、术语规则、翻译配置和非敏感 MinerU 请求配置，这样默认版本切换后历史 job 仍能按创建时资源复现。
- 作为维护者和集成方，我希望资源发布、回滚、job 运维和 artifact 下载等高风险动作都有最小操作者上下文和审计流水，这样能追踪谁在什么时候对什么目标做了什么。
- 作为生产部署维护者，我希望把 jobs metadata 显式切到 MySQL，同时继续让 PDF、DOCX、MinerU zip 等大文件留在 artifact storage，避免数据库承载二进制文件。
- 作为生产部署维护者，我希望发布前有 `.env.example`、readiness、JSON metrics、MySQL metadata shadow copy / validate、release check 和真实外部联调 runbook，这样能用同一套基线判断单实例后端是否可上线。
- 作为维护者和集成方，我希望 jobs 产物能暴露稳定的大小、hash 和下载诊断，这样可以区分缺失文件、路径错误和内容被改动，而不是只看到模糊下载失败。
- 作为维护者，我希望模板、术语规则集和翻译配置后续都复用同一套版本状态、默认指针和回滚规则，避免三套资源各自实现不一致的发布语义。
- 作为内部操作员，我希望上传原始 PDF 后能在工作台看到任务进度、失败阶段、下载入口和重试操作，而不是只拿到一个后台脚本结果。
- 作为交付负责人，我希望系统能用 Golden Sample 明确报告真实可运行样本数、主链路成功率、失败阶段和人工质量结论，而不是把“能生成 Word”和“质量达标”混在一起。

## 为什么需要

当前仓库的核心转换能力已经足够强，但原始使用方式偏向本地脚本和人工操作，缺少稳定 API、状态可见性和最小运维闭环。没有后端产品化，这些能力难以被前端、自动化脚本或其他服务可靠复用。

## 怎么解决

提供一个以 `FastAPI + BackgroundTasks + metadata repository + conversion library` 为核心的后端表面：

- `POST /api/v1/files/upload-url` 和 `PUT /api/v1/files/{file_id}/content` 提供 PDF 上传授权与本地代理上传
- `POST /api/v1/document-jobs` 提供 P0 PDF -> Word 任务创建，默认 `direct_pdf_to_word`
- `GET /api/v1/document-jobs/*` 提供任务列表、详情、事件、重试、取消、归档、download-url 和短期下载
- `document_jobs` Worker 保存 MinerU raw result、DocumentIR v2、图片资产和生成 Word，并把失败阶段、错误码、错误消息和 trace 事件落到任务详情
- Golden Sample 回归和人工质量 triage 区分主链路可运行、Word 可打开、可编辑质量和版式/语义质量
- `POST /api/v1/jobs` 接收 MinerU 输出 zip
- `POST /api/v1/jobs/pdf` 接收原始 PDF，并把任务送进 MinerU；callback 成功后会短暂经过 `parsed`，随后自动恢复结果 zip 并继续后处理到 `completed/failed`
- `POST /api/v1/mineru-callbacks/result` 承载 callback ingress、安全校验和结果收口
- `GET /api/v1/jobs/*` 提供状态、事件、产物和下载入口
- jobs artifact 合同记录 logical path、`size_bytes` 和 `sha256:<hex>` fingerprint，下载本地文件前校验路径、存在性和 fingerprint，并提供稳定诊断状态
- `translation_mode=en2zh` 在同一条任务主链里接入翻译
- `GET /api/v1/templates*` 提供默认模板、绑定配置和 Template Version 状态；admin-only templates API 支持模板创建、元数据更新、文件替换、删除，以及 MySQL resource service 下的版本 draft、发布、设默认和禁用
- `GET/PUT/POST /api/v1/term-rule-sets*` 在 MySQL resource service 下提供 Term Rule Set draft、publish、set-default 和 rollback；draft 更新不影响 live runtime，默认 published 版本同步到 `term_rules_store.json` 与 `runtime_subscripts_dictionary.yaml`
- `GET/PUT/POST /api/v1/translation-profiles*` 在 MySQL resource service 下提供 Translation Profile draft、publish、set-default 和 rollback；`en2zh` 执行时默认 published profile 可覆盖模型、目标语言、领域、prompt 版本和分批阈值
- `translation_mode=en2zh` 成功任务除 `translation_request` 外会登记 `translation_trace` artifact，记录 segment 原文、模型输入、AI 初译、最终渲染文本和可选 Translation Profile 快照
- MySQL resource mode 下 `POST /api/v1/jobs` / `POST /api/v1/jobs/pdf` 在创建期绑定默认或指定 published Template Version、Term Rule Version，以及 `en2zh` Translation Profile Version，并把摘要写入 `JobRecord.resource_snapshot`、创建响应、详情响应和 `job_created` 事件
- 后台 stage 对 snapshot job 只按创建时 snapshot materialize 模板 DOCX、job-local `runtime_subscripts_dictionary.yaml` 和 Translation Profile；PDF 在线提交使用 snapshot 中的非敏感 MinerU 请求配置
- `require_admin_actor()`、`require_jobs_actor()`、`require_job_ops_actor()` 在保留既有 token 校验语义的同时派生 `ActorContext`，并对 Template / Term Rule Set / Translation Profile 发布动作、job retry / cancel / cleanup-local-files、artifact download 成功路径写入独立 `AuditEvent`
- `health/live`、`health/ready` 和本地运维动作提供运行时观测与恢复入口；`health/ready` 额外报告 artifact root 可写性、磁盘余量、默认资源版本标签和 MySQL schema bootstrap 状态
- `GET /api/v1/health/metrics` 返回 JSON 运维计数，覆盖 metadata store、artifact storage、worker mode、job status counts、stage message counts、resource version counts 和 audit event count
- `JOBS_REPOSITORY_BACKEND=file/database/mysql` 提供本地文件、sqlite 和 MySQL 三种 jobs metadata store，服务层统一依赖 repository protocols
- `scripts/ops/shadow_copy_metadata_to_mysql.py` 提供 file -> MySQL metadata 空目标 shadow copy 和 validate-only 校验，artifact 二进制不写入 MySQL
- `scripts/ops/check_release.py` 聚合 OpenAPI snapshot、health/metrics、metadata migration、job workflow、MySQL fake smoke 和 logging tests，作为发布前本地基线
- `.env.example`、runbook 和 runtime observability 文档覆盖 MySQL metadata、artifact storage、worker mode、access token、callback URL、`LOG_FORMAT=json`、release check 和真实 MinerU / LLM 外部联调步骤
- resource versioning 内部 service 统一 `draft/published/disabled/superseded`、不可变发布版本、默认指针和 published-only 解析；Template Profile、Term Rule Set 和 Translation Profile 已接入

## 边界

- 当前支持两条入口：
  - 上传 PDF 文件 -> 创建 `document_jobs` -> Worker / MinerU / DocumentIR / Word renderer -> 下载 DOCX
  - 上传 MinerU 输出 zip -> 后处理 -> 生成 DOCX
  - 上传原始 PDF -> 成功提交 MinerU -> 接收 callback -> 恢复 `parsed_result_package` -> 后处理 -> 生成 DOCX
- P0 document_jobs 当前能证明主链路可交付，但 Golden Sample 正式规模仍 blocked：4 个正式匹配 PDF 中只有 1 个跑过真实链路，尚未达到 10-20 份样本成功率 `>= 90%` 和人工质量验收。
- `en2zh_pdf_to_word` 当前按实验能力发布，不阻塞 P0 `direct_pdf_to_word`。
- 当前默认仍是 file backend，但 jobs metadata 已有 sqlite-backed database adapter、MySQL adapter 和 shadow copy / switch 能力，artifact 已有本地对象目录 adapter 和 shadow upload / switch 能力；仍不包含 PostgreSQL，也未把 artifact 二进制写入 MySQL。
- artifact 合同已覆盖新登记产物的 `size_bytes` / `sha256`、本地下载诊断和 local + object retention dry-run；旧记录缺少 fingerprint 时保持兼容，不强制 backfill，不执行真实删除，也不新增 S3 / OSS / MinIO。
- MySQL adapter 当前覆盖 jobs、events、files、stage messages、`resource_versions`、`resource_default_versions` 和 `audit_events`；schema bootstrap、file -> MySQL 空目标 shadow copy / validate、fake MySQL release smoke 和部署 runbook 已进入当前运维基线。真实外部 MySQL 服务 smoke 仍按 runbook 手工执行，Alembic / SQLAlchemy 迁移体系仍不在当前范围。
- 当前 metrics 是 JSON endpoint，不接 Prometheus、Grafana、OpenTelemetry、ELK 或外部告警平台；release check 默认不依赖真实 MinerU、OpenAI 或公网。
- resource versioning 当前只提供内部模型、repository protocol、MySQL 持久化和 service 状态机；不提供通用 HTTP router。Template Profile、Term Rule Set 与 Translation Profile 已实现具体管理和版本发布 API，jobs 在 MySQL resource mode 下通过不可变 resource snapshot 消费 published 版本。
- 当前模板接口已支持 Template Profile CRUD、文件替换和 MySQL-backed 版本管理；file/sqlite backend 保持 manifest 兼容，版本发布状态接口要求 MySQL resource service。
- 当前术语规则在 MySQL backend 下支持 Term Rule Set 草稿、发布、设默认和回滚；file/sqlite backend 仍保持 legacy live store 写入兼容。snapshot job 会把创建时 Term Rule Version materialize 成 job-local YAML，避免历史 job 读取全局最新 runtime YAML。
- 当前翻译配置在 MySQL backend 下支持 `electronics-en2zh` Translation Profile 草稿、发布、设默认和回滚；file/sqlite backend 下 profile 管理接口返回 503，但现有 settings / `.env` 翻译路径仍保持兼容。MySQL resource mode 下 `en2zh` job 创建时绑定 Translation Profile Version，`direct` job 不绑定翻译配置。
- Job Resource Snapshot 不回填历史 job；旧 job 和 file/sqlite legacy job 允许 `resource_snapshot=null`。file/sqlite backend 显式传 `template_version`、`term_rule_set_id/version` 或 `translation_profile_id/version` 时返回 503。
- snapshot 不保存 API key、MinerU token、callback token、完整 prompt 文本或 term-rule payload；`artifact_ids` 只记录 source artifact alias（`source_package` / `source_pdf`），不新增独立 artifact id 体系。
- 审计基线当前只表达 `admin`、`jobs`、`anonymous` 三类 actor；不新增 SSO、用户表、多租户字段、资源所有者校验、审计查询 HTTP API 或审计 UI。open 下载始终写 anonymous actor，不接受匿名请求用 `X-Actor-Id` 自报身份。
- jobs API 仍只支持 `direct` / `en2zh`，不新增 `zh2en` / `zh2ru` 或 `source_language` / `target_language` 创建参数。

## 变更日志

- 2026-06-03：补入 P0 `document_jobs` PDF -> Word 主链路、内部工作台、Golden Sample 质量基线和当前 blocked 边界。

## 变更日志

- 2026-05-29：补入 Operations Readiness and Test Baseline；新增 `health/metrics` JSON counters，扩展 readiness artifact / resource / MySQL schema 字段，补入 file -> MySQL metadata shadow copy / validate、`.env.example`、release check 和运维文档基线。
- 2026-05-29：补入 Permission and Audit Baseline；高风险资源动作、job ops 和 artifact download 成功路径写入独立 `AuditEvent`，actor 从现有 admin/jobs/open token 边界派生，不引入 SSO、多租户或审计查询 API。
- 2026-05-29：补入 Job Resource Snapshot Binding；MySQL resource mode 下 job 创建绑定 Template / Term Rule / `en2zh` Translation Profile published versions、非敏感 MinerU snapshot 和 source artifact alias，stage 按创建时 snapshot materialize runtime resources。
- 2026-05-29：补入 Translation Profile and Segment Trace；翻译配置从 settings-only 扩展为 MySQL-backed draft / published / default pointer / rollback，并在 `en2zh` job 中登记 `translation_trace` artifact。
- 2026-05-29：补入 Term Rule Set versioning；术语规则从直接 live store 覆盖扩展为 MySQL-backed draft / published / default pointer / rollback，默认 published 版本同步到 legacy runtime store。
- 2026-05-29：补入 Template Profile versioning；模板 API 从只读元数据扩展为支持 Template Profile CRUD、DOCX 文件替换，以及 MySQL-backed 版本创建、发布、设默认和禁用。
- 2026-05-29：补入 resource versioning foundation；资源版本底座提供统一状态机、默认指针、回滚和 published-only 解析，模板 / 术语 / 翻译配置按后续子 feature 接入。
- 2026-05-28：补入 local artifact contract hardening；新登记 jobs artifact 返回 `size_bytes` / `sha256`，本地下载区分路径非法、缺失文件和 fingerprint mismatch，retention 当前只输出 dry-run 候选。
- 2026-05-28：补入 MySQL metadata store；`JOBS_REPOSITORY_BACKEND=mysql` 可保存 jobs metadata、stage messages 和 resource_versions 基础表，readiness 可报告 MySQL backend，artifact 二进制仍由独立 storage 管理。
- 2026-05-28：能力边界升级为 PDF 在线链路可从 callback 自动推进到 DOCX 完成态；同时补入 jobs metadata database adapter、artifact local_object adapter、shadow copy/upload 和 worker/queue 不引入的当前决策。
- 2026-05-18：能力边界从“PDF 在线提交前半程”升级到“已接 callback ingress 与安全收口”的早期状态。
