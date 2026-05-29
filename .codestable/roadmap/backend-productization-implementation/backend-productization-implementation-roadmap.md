---
doc_type: roadmap
slug: backend-productization-implementation
status: active
created: 2026-05-28
last_reviewed: 2026-05-29
tags: [backend, productization, mysql, templates, term-rules, translation, operations]
related_requirements: [fastapi-backend-productization]
related_architecture: [architecture-index, backend-fastapi-service]
---

# 后端产品化实施路线图

## 1. 背景

当前 FastAPI 后端已经具备 PDF / MinerU / DOCX 主链路、job 事件、artifact 合同、stage dispatcher、stage message store、metadata adapter 和本地 artifact adapter 的基础边界。下一阶段目标不是继续堆接口，而是把公司内部生产使用所需的业务 metadata、模板 Profile、术语版本、翻译追踪、权限审计和运维测试固化下来。

本 roadmap 承接 `.codestable/brainstorms/backend-productization-risk-check/brainstorm.md` 的结论：系统定位为“单实例生产化的电子元器件 PDF 转 Word 编排服务”。业务 metadata 以 MySQL 为真源，大文件 artifact 继续存本地文件系统；不做公司 / 租户隔离，不引入 Redis / Celery / 对象存储。

## 2. 范围与明确不做

### 本 roadmap 覆盖

- MySQL 业务 metadata 基线：jobs、events、stage messages、artifacts、resource versions。
- 本地 artifact 合同加固：逻辑路径、hash、大小、retention、下载诊断。
- Template Profile 版本管理：`docx + layout + render_policy`。
- Term Rule Set 草稿、发布、回滚和任务绑定。
- Job 创建时的资源版本快照：模板、术语、翻译配置、MinerU 标识、artifact ids。
- Translation Profile 和 segment 追踪，为后续人工校对预留。
- 最小权限和审计：上传、发布、回滚、retry、cleanup、下载。
- 部署、日志、readiness、metrics、runbook 和测试基线。

### 明确不做

- 不做多租户 / 公司隔离；不同公司差异通过模板 Profile 表达。
- 不引入 Redis、Celery、RQ 或独立 worker。
- 不引入 S3 / OSS / MinIO；artifact 仍在本地文件系统。
- 不做前端页面和可视化模板编辑器。
- 不做人工翻译校对工作台，只预留数据结构和接口边界。
- 不重写 MinerU 解析、Word 渲染和版式算法。
- 不把术语规则和翻译配置塞进 Template Profile。

## 3. 模块拆分（概设）

```text
backend-productization-implementation
├── mysql metadata foundation：业务 metadata 真源和迁移基线
├── local artifact storage：本地大文件存储、校验、retention
├── resource versioning：模板 / 术语 / 翻译配置的通用版本协议
├── template profiles：docx + layout + render_policy 的版本化资源
├── term rule sets：草稿编辑、发布版本、回滚和查询
├── job orchestration snapshot：任务创建时绑定资源版本并写入快照
├── translation trace：翻译配置、segment、AI 结果和后续人工校对预留
├── permission and audit：最小角色、actor 上下文和审计事件
└── operations quality：部署、日志、readiness、metrics、测试和 runbook
```

### mysql metadata foundation

- **职责**：把业务 metadata 的正式真源迁到 MySQL，覆盖 job snapshot、events、files/artifacts、stage messages 和资源版本基础表。
- **不承担**：不存 PDF / DOCX / zip 二进制，不决定模板 / 术语的业务编辑流程。
- **承载的子 feature**：`mysql-metadata-foundation`
- **触碰的现有代码 / 模块**：`app/repositories/`、`app/core/config.py`、`app/main.py`、迁移脚本、测试构造。

### local artifact storage

- **职责**：继续用本地文件系统保存大文件，同时固定文件 hash、大小、逻辑路径、物理路径解析、retention 和下载诊断。
- **不承担**：不引入对象存储，不处理资源版本发布语义。
- **承载的子 feature**：`local-artifact-contract-hardening`
- **触碰的现有代码 / 模块**：`app/services/jobs/artifacts.py`、`app/services/jobs/artifact_storage.py`、下载 router、runbook。

### resource versioning

- **职责**：为模板、术语、翻译配置建立统一版本状态、不可变发布版本、默认版本和回滚口径。
- **不承担**：不规定每类资源内部字段细节，不暴露通用 HTTP API。
- **承载的子 feature**：`resource-versioning-foundation`
- **触碰的现有代码 / 模块**：资源版本模型 / repository protocol / MySQL adapter / `ResourceVersionService`，后续模板、术语、翻译模块复用。

### template profiles

- **职责**：管理 `TemplateProfile` 和 `TemplateVersion`，每个版本绑定 `docx + layout + render_policy`，支持上传、校验、发布、设默认和停用。
- **不承担**：不管理术语规则、翻译配置，不做可视化编辑器。
- **承载的子 feature**：`template-profile-versioning`
- **触碰的现有代码 / 模块**：`app/services/templates/`、`app/api/v1/routers/templates.py`、`app/schemas/templates.py`、template runtime 配置加载。

### term rule sets

- **职责**：管理术语规则草稿和已发布版本，支持 CRUD 草稿、发布、回滚、查询当前默认发布版本。
- **不承担**：不直接决定翻译模型，不绑定某个模板 Profile。
- **承载的子 feature**：`term-rule-set-versioning`
- **触碰的现有代码 / 模块**：`app/services/term_rules/`、`app/api/v1/routers/term_rules.py`、term rule runtime 配置加载。

### job orchestration snapshot

- **职责**：创建任务时解析并锁定实际使用的模板版本、术语版本、翻译配置版本、MinerU 标识和 artifact ids，保证历史任务可复现。
- **不承担**：不提供模板 / 术语编辑能力，不执行具体 Word 渲染算法。
- **承载的子 feature**：`job-resource-snapshot-binding`
- **触碰的现有代码 / 模块**：jobs ingest router、`JobCommandService`、stage service、conversion request builder、job schema。

### translation trace

- **职责**：把翻译从一次性函数调用升级为可追踪资源，记录 `TranslationProfile`、segment 原文、AI 初译、最终用于渲染的文本和模型 / prompt 版本。
- **不承担**：不做人工校对 UI，不强制当前流程停在校对态。
- **承载的子 feature**：`translation-profile-and-segment-trace`
- **触碰的现有代码 / 模块**：`translation_runtime.py`、`llm_client.py`、conversion entrypoint、job artifacts。

### permission and audit

- **职责**：建立最小 actor 上下文、角色和审计事件，覆盖资源发布、回滚、retry、cancel、cleanup 和下载。
- **不承担**：不做多租户、不接复杂 SSO。
- **承载的子 feature**：`permission-and-audit-baseline`
- **触碰的现有代码 / 模块**：API dependencies、admin ops、resource service、audit repository。

### operations quality

- **职责**：让部署和排障可执行，覆盖 `.env.example`、MySQL migration、数据目录、callback URL、readiness、metrics、结构化日志、测试套件和 runbook。
- **不承担**：不引入外部监控平台。
- **承载的子 feature**：`operations-readiness-and-test-baseline`
- **触碰的现有代码 / 模块**：health service、logging、docs、tests、deployment scripts。

## 4. 模块间接口契约 / 共享协议（架构层详设）

### 4.1 Resource version 通用协议

**方向**：template / term-rule / translation services → job orchestration  
**形式**：共享数据库表 + service 查询

**契约**：

```python
class ResourceVersionStatus(str, Enum):
    draft = "draft"
    published = "published"
    disabled = "disabled"
    superseded = "superseded"

class ResolvedResourceVersion(BaseModel):
    resource_type: Literal["template", "term_rule_set", "translation_profile"]
    resource_id: str
    version: str
    status: Literal["published"]
    snapshot_hash: str
    payload_ref: str | None
```

**约束**：

- 当前底座实现为内部 service；资源子模块负责 payload 结构、hash 计算和对外 API。
- job 只能绑定 `published` 版本。
- 已被 job 引用的 `published` 版本不可原地修改；修改必须发布新版本。
- 回滚不是改旧版本内容，而是把默认指针切回旧的 `published` 版本。
- 每个资源版本必须有 `snapshot_hash`，用于判断历史任务是否可复现。

### 4.2 Job 创建资源解析协议

**方向**：jobs API → JobCommandService → resource services  
**形式**：函数调用

**契约**：

```python
class JobCreateOptions(BaseModel):
    template_id: str | None = None
    template_version: str | None = None
    term_rule_set_id: str | None = None
    term_rule_set_version: str | None = None
    translation_profile_id: str | None = None
    translation_profile_version: str | None = None
    translation_mode: Literal["direct", "en2zh"] = "direct"
    document_language: Literal["auto", "zh", "en"] = "auto"

class JobResourceSnapshot(BaseModel):
    template: ResolvedResourceVersion
    term_rule_set: ResolvedResourceVersion
    translation_profile: ResolvedResourceVersion | None
    mineru: dict[str, str | None]
    artifact_ids: dict[str, str]
```

**约束**：

- 未传 `template_id` 时使用默认 Template Profile 的默认发布版本。
- 未传 `term_rule_set_id` 时使用默认 Term Rule Set 的默认发布版本。
- `translation_mode=direct` 时 `translation_profile` 可以为 null。
- job 创建成功后，资源快照不可随默认版本变更而变化。
- file/sqlite backend 不传 versioned resource selection 时保持 legacy 路径；显式传 `template_version`、`term_rule_set_id/version` 或 `translation_profile_id/version` 时返回 503。
- `artifact_ids` 当前只记录 source artifact alias（`source_package` / `source_pdf`），不引入独立 artifact id 体系。
- 当前 jobs API 不扩展 `zh2en` / `zh2ru` 或 `source_language` / `target_language`。

### 4.3 Template Profile API 合同

**方向**：前端 / 管理脚本 → templates service  
**形式**：HTTP API

**契约**：

```text
GET  /api/v1/templates
GET  /api/v1/templates/{template_id}
POST /api/v1/templates
POST /api/v1/templates/{template_id}/versions
POST /api/v1/templates/{template_id}/versions/{version}/publish
POST /api/v1/templates/{template_id}/versions/{version}/set-default
POST /api/v1/templates/{template_id}/versions/{version}/disable
```

`TemplateVersion` 最小字段：

```json
{
  "template_id": "datasheet-default",
  "version": "1.0.0",
  "status": "published",
  "docx_artifact_id": "artifact-id",
  "layout_config": {},
  "render_policy": {},
  "snapshot_hash": "sha256:...",
  "created_by": "actor-id",
  "published_at": "2026-05-28T00:00:00+08:00"
}
```

**错误码**：`template_not_found`、`template_version_not_found`、`template_version_not_published`、`invalid_template_docx`、`invalid_render_policy`、`template_version_in_use`。

### 4.4 Term Rule Set API 合同

**方向**：前端 / 管理脚本 → term rules service  
**形式**：HTTP API

**契约**：

```text
GET  /api/v1/term-rule-sets
GET  /api/v1/term-rule-sets/{set_id}
GET  /api/v1/term-rule-sets/{set_id}/draft
PUT  /api/v1/term-rule-sets/{set_id}/draft/rules
POST /api/v1/term-rule-sets/{set_id}/publish
POST /api/v1/term-rule-sets/{set_id}/versions/{version}/set-default
POST /api/v1/term-rule-sets/{set_id}/rollback
```

`TermRuleVersion` 最小字段：

```json
{
  "term_rule_set_id": "electronics-default",
  "version": "2026.05.28-1",
  "status": "published",
  "rule_count": 1200,
  "snapshot_hash": "sha256:...",
  "published_by": "actor-id",
  "publish_reason": "补充电容/电阻参数术语",
  "published_at": "2026-05-28T00:00:00+08:00"
}
```

**约束**：

- 草稿可编辑；发布版本不可编辑。
- 任务只读取发布版本，不读取草稿。
- rollback 只切默认发布版本指针，不修改历史版本内容。

### 4.5 Stage message MySQL 协议

**方向**：JobStageService → StageMessageStore  
**形式**：数据库表 + repository protocol

**契约**：

```python
class StageMessageRecord(BaseModel):
    message_id: str
    job_id: str
    stage: str
    status: Literal["pending", "running", "succeeded", "failed"]
    payload: dict
    idempotency_key: str
    attempt_count: int
    locked_at: datetime | None
    last_error_code: str | None
    last_error_message: str | None
```

**约束**：

- `pending/running` 可在进程启动时 replay。
- `failed` 不自动 replay，只能由 retry 创建新 message 或显式恢复。
- 同一 `idempotency_key` 重复执行不得产生重复 artifact 或重复终态事件。
- `completed/canceled` job 不接受会倒退状态的 stage message。

### 4.6 Audit event 协议

**方向**：API dependencies / services → audit repository  
**形式**：数据库表 + business log

**契约**：

```python
class AuditEvent(BaseModel):
    audit_id: str
    actor_id: str | None
    actor_role: str | None
    action: str
    target_type: str
    target_id: str
    reason: str | None
    trace_id: str
    created_at: datetime
```

**必须审计的动作**：

- template publish / set-default / disable
- term-rule publish / rollback / set-default
- job retry / cancel / cleanup-local-files
- artifact download

### 4.7 Readiness / metrics 诊断协议

**方向**：health service → 调用方 / 运维  
**形式**：HTTP API

**契约**：

```json
{
  "status": "ok",
  "metadata_store": "mysql",
  "artifact_storage": "local_file",
  "worker_mode": "in_process",
  "stage_spool_pending_messages": 0,
  "stage_spool_running_messages": 0,
  "stage_spool_failed_messages": 0,
  "artifact_root_writable": true,
  "artifact_disk_free_bytes": 0,
  "default_template_version": "datasheet-default@1.0.0",
  "default_term_rule_version": "electronics-default@2026.05.28-1"
}
```

**约束**：

- readiness 不自动修复 failed message。
- metrics 可以先是 JSON endpoint，不要求马上接 Prometheus。
- health 不暴露 secret、绝对私密路径或完整客户文件名。

## 5. 子 feature 清单

1. **mysql-metadata-foundation** — 建立 MySQL 业务 metadata 基线，使现有 job 主链可在 MySQL metadata store 下跑通。
   - 所属模块：mysql metadata foundation
   - 依赖：无
   - 状态：done
   - 对应 feature：`2026-05-28-mysql-metadata-foundation`
   - 备注：最小闭环；不改变 artifact 仍在本地文件系统的事实。

2. **local-artifact-contract-hardening** — 加固本地 artifact 合同，补齐 hash、大小、retention、下载诊断和缺失文件错误。
   - 所属模块：local artifact storage
   - 依赖：mysql-metadata-foundation
   - 状态：done
   - 对应 feature：`2026-05-28-local-artifact-contract-hardening`

3. **resource-versioning-foundation** — 建立资源版本通用协议，统一 `draft/published/disabled/superseded`、默认指针和不可变发布版本规则。
   - 所属模块：resource versioning
   - 依赖：mysql-metadata-foundation
   - 状态：done
   - 对应 feature：`2026-05-28-resource-versioning-foundation`

4. **template-profile-versioning** — 实现 Template Profile 版本管理，支持上传 docx、layout、render_policy、发布和设默认。
   - 所属模块：template profiles
   - 依赖：resource-versioning-foundation, local-artifact-contract-hardening
   - 状态：done
   - 对应 feature：`2026-05-29-template-profile-versioning`

5. **term-rule-set-versioning** — 实现术语规则草稿、发布、回滚和默认版本查询，任务只读取发布版本。
   - 所属模块：term rule sets
   - 依赖：resource-versioning-foundation
   - 状态：done
   - 对应 feature：`2026-05-29-term-rule-set-versioning`

6. **translation-profile-and-segment-trace** — 建立 Translation Profile 与 segment 追踪，保存 AI 初译和最终渲染文本，为人工校对预留。
   - 所属模块：translation trace
   - 依赖：resource-versioning-foundation
   - 状态：done
   - 对应 feature：`2026-05-29-translation-profile-and-segment-trace`

7. **job-resource-snapshot-binding** — 任务创建时解析模板、术语、翻译配置发布版本，并写入不可变资源快照。
   - 所属模块：job orchestration snapshot
   - 依赖：template-profile-versioning, term-rule-set-versioning, translation-profile-and-segment-trace
   - 状态：done
   - 对应 feature：`2026-05-29-job-resource-snapshot-binding`

8. **permission-and-audit-baseline** — 建立最小 actor / role / audit event，保护发布、回滚、retry、cleanup 和下载等高风险动作。
   - 所属模块：permission and audit
   - 依赖：resource-versioning-foundation, job-resource-snapshot-binding
   - 状态：done
   - 对应 feature：`2026-05-29-permission-and-audit-baseline`

9. **operations-readiness-and-test-baseline** — 补齐部署说明、MySQL migration、readiness、metrics、结构化日志、状态机测试和真实链路 smoke。
   - 所属模块：operations quality
   - 依赖：mysql-metadata-foundation, job-resource-snapshot-binding, permission-and-audit-baseline
   - 状态：done
   - 对应 feature：`2026-05-29-operations-readiness-and-test-baseline`

**最小闭环**：第 1 条 `mysql-metadata-foundation` 做完后，现有 PDF / MinerU / DOCX 主链可在 MySQL metadata store + 本地 artifact storage 下端到端跑通，并且 readiness 能报告当前 metadata store 为 MySQL。第 2 条完成后，新登记 artifact 已带 `size_bytes` / `sha256`，本地下载能区分路径非法、文件缺失和 fingerprint mismatch，retention 已有 local + object dry-run 候选。

## 6. 排期思路

先做 MySQL metadata，是因为模板、术语、翻译和审计都依赖稳定的业务 metadata 真源。第二步加固 artifact，是为了保证大文件仍放本地时也能定位缺失、损坏和清理问题。随后先抽通用资源版本协议，再分别落模板、术语和翻译配置，避免三套资源各自发明版本状态。最后把资源版本绑定到 job 快照，再补权限审计和运维测试。

这个顺序刻意不先做模板 CRUD，因为模板管理如果没有资源版本协议和 artifact 合同，会很快退化成“上传一个文件路径”的临时实现。

## 7. 观察项

- MySQL metadata foundation 已落地轻量 schema bootstrap 和 repository adapter；operations baseline 已补入 file -> MySQL 空目标 shadow copy / validate、fake MySQL release smoke 和 runbook。SQLAlchemy / Alembic 与真实外部 MySQL 自动 smoke 仍不在当前范围。
- Local artifact contract hardening 已落地大小 / hash / 下载诊断 / dry-run 计划；真实 artifact 删除、删除审计和旧记录 fingerprint backfill 仍留给后续权限或运维 feature。
- Resource versioning foundation 已落地通用模型、MySQL `resource_versions` / `resource_default_versions`、默认指针和 service 状态机；Template Profile、Term Rule Set 与 Translation Profile 管理 API 已落地。
- Template Profile versioning 已落地模板 CRUD / 文件替换和 MySQL-backed Template Version draft/publish/set-default/disable；MySQL resource mode 下 job 创建已可绑定 Template Version snapshot。
- Term Rule Set versioning 已落地默认术语规则集 `electronics-default` 的 draft / publish / set-default / rollback；MySQL versioned mode 下 legacy term-rules 写入口被保护，job 创建已可绑定 Term Rule Version snapshot 并在 stage 物化 job-local YAML。
- Translation Profile and Segment Trace 已落地默认翻译配置 `electronics-en2zh` 的 draft / publish / set-default / rollback；`en2zh` job 会登记 `translation_trace` artifact，MySQL resource mode 下 job 创建已可绑定 Translation Profile Version snapshot。
- Job Resource Snapshot Binding 已落地 MySQL-only 严格 snapshot：创建期绑定 published Template / Term Rule / `en2zh` Translation Profile versions、非敏感 MinerU 请求配置和 source artifact alias；file/sqlite 不传 versioned 参数时保持 legacy 路径，显式 versioned selection 返回 503。
- Permission and Audit Baseline 已落地最小 actor / role / audit event：高风险资源动作、job ops 和 artifact download 成功路径写入独立 `AuditEvent`；open 下载保持 anonymous，不做 SSO、多租户或审计查询 API。
- Operations Readiness and Test Baseline 已落地 `.env.example`、`health/ready` artifact / resource / MySQL schema 扩展、`health/metrics` JSON counters、file -> MySQL metadata shadow copy / validate、release check 聚合和运维文档基线；不引入 Prometheus、Alembic / ORM migration 或多实例 worker。
- `mineru-online-ingestion` 仍有 callback postprocess / recovery / observability planned 条目；本 roadmap 不替它回写状态，但 job snapshot 和 MySQL metadata 会影响其后续设计。
- 如果公司后续要求 SSO、用户表、多租户、资源所有者校验或审计 UI，应另起 feature 或 roadmap，不混进当前 MVP。
- 人工校对工作台不在本 roadmap 内；本 roadmap 只预留 segment 和最终文本记录。
- 当前 architecture 已由各子 feature acceptance 阶段回写为现状；后续 roadmap 只记录跨 feature 规划，不承载实现细节。

## 8. 变更日志

- 2026-05-29：`operations-readiness-and-test-baseline` 完成验收回写；roadmap items 标记 done，主文档同步为已落地 readiness/metrics、MySQL metadata shadow copy / validate、release check、`.env.example` 和运维文档基线。
- 2026-05-29：`operations-readiness-and-test-baseline` 启动 feature design；roadmap items 标记 in-progress，设计草案覆盖 deployment env、MySQL migration baseline、readiness/metrics、release check、日志和 smoke 测试边界。
- 2026-05-29：`permission-and-audit-baseline` 完成验收回写；roadmap items 标记 done，主文档同步为已落地最小 ActorContext、AuditEvent、file/sqlite/MySQL 审计持久化和高风险动作成功审计。
- 2026-05-29：`permission-and-audit-baseline` 启动 feature design；roadmap items 标记 in-progress，设计草案覆盖最小 ActorContext、AuditEvent、审计持久化和高风险动作挂载点。
- 2026-05-29：`job-resource-snapshot-binding` 完成验收回写；roadmap items 标记 done，主文档同步为已落地 MySQL-only 严格 Job Resource Snapshot、file/sqlite legacy 路径、job-local term-rule YAML materialization 和 source artifact alias 边界。
- 2026-05-29：`translation-profile-and-segment-trace` 完成验收回写；roadmap items 标记 done，主文档同步为已落地 Translation Profile draft / publish / set-default / rollback 与 `translation_trace` artifact。
- 2026-05-29：`translation-profile-and-segment-trace` 启动 feature design / implementation，roadmap items 标记 in-progress。
- 2026-05-29：`term-rule-set-versioning` 完成验收回写；roadmap items 标记 done，主文档同步为已落地 Term Rule Set draft / publish / set-default / rollback 和 legacy 写保护。
- 2026-05-29：`template-profile-versioning` 完成验收回写；roadmap items 标记 done，主文档同步为已落地 Template Profile CRUD 和 MySQL-backed version 管理边界。
- 2026-05-29：`template-profile-versioning` 启动 feature design / implementation，roadmap items 标记 in-progress。
- 2026-05-29：`resource-versioning-foundation` 完成验收回写；roadmap items 标记 done，主文档同步为已落地内部资源版本 service 和默认指针边界。
- 2026-05-28：`local-artifact-contract-hardening` 完成验收回写；roadmap items 标记 done，并同步主文档中的 feature 状态与后续衔接边界。
- 2026-05-28：根据后端产品化脑暴和风险查漏结论创建 roadmap，拆出 MySQL metadata、模板 Profile、术语版本、翻译追踪、权限审计和运维测试九条实施清单。
