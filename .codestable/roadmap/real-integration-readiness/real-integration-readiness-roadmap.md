---
doc_type: roadmap
slug: real-integration-readiness
status: active
created: 2026-06-07
last_reviewed: 2026-06-07
tags: [phase6, operations, real-integration, alerts, provider-cancellation, s3, scheduler, quota]
related_requirements: [fastapi-backend-productization]
related_architecture: [backend-fastapi-service, conversion-flow]
---

# Phase 6 Real Integration Readiness

## 1. 背景

Phase 5 已把 Ops 高风险动作推进到 fake、dry-run、preview、signed plan、cleanup lock、structured audit details、quota preflight 和前端可视化控制。系统现在能证明目标选择、确认短语、dedupe、audit details、run history 和 dry-run history 的基础合同。

Phase 6 的目标不是一次性打开所有真实外部动作，而是把真实 Slack/email/webhook delivery、真实 provider cancellation、真实 S3 delete、autonomous cleanup scheduler 和 quota enforcement 运维化拆成一组可独立验收的受控子 feature。每个真实动作都必须先有 disabled-by-default 开关、secret-ref 边界、fake/local parity、timeout/error/idempotency 合同、结构化审计和 rollback/runbook，才能进入真实执行。

## 2. 范围与明确不做

### 本 roadmap 覆盖

- 真实集成控制面：按能力分开的 feature flag、kill switch、readiness gate 和 release gate。
- 真实 Ops alert delivery：从 staged destination config 到 Slack/webhook/email adapter 的受控发送。
- 真实 provider cancellation：先验证 MinerU/provider cancellation API 语义，再实现精确目标的真实取消 adapter。
- 真实 S3 delete：从 fake contract / LocalStack parity 到受控真实对象删除。
- Cleanup scheduler execution：从 manual scheduler dry-run 推进到 disabled-by-default 的自动执行。
- Quota enforcement 运维硬化：当前后端阻断/override 能力后的 UI、审计展示、配置检查和回滚口径。
- 结构化审计、delivery/delete/cancel history、runbook 和 release verification。

### 明确不做

- 不在 roadmap 本身执行任何真实外部调用、删除、scheduler loop 或 provider cancellation。
- 不把所有真实集成放进一个总开关；每类能力必须独立 enable、独立回滚。
- 不把 secret value 写进 settings JSON、API response、audit reason、audit details、history 或前端状态。
- 不做 bulk provider cancellation、delete-all cleanup、all-alert implicit delivery；所有执行都必须精确目标。
- 不扩展 SSO、多租户权限模型或组织级 RBAC；当前仍沿用 admin/operator JWT 角色。
- 不把 real provider cancellation 当作已知可行能力；必须先完成 provider API 语义验证。
- 不把 autonomous scheduler execute 作为 cleanup history 或 signed plan 的默认行为；默认仍为 dry-run。

## 3. 模块拆分（概设）

```text
real-integration-readiness
├── integration-control-plane：真实外部动作的开关、readiness、kill switch 和 release gate
├── alert-delivery-providers：Slack/email/webhook 真实发送 adapter、destination allowlist 和 delivery history
├── provider-cancellation-adapters：MinerU/provider cancellation API 语义验证与真实 adapter
├── cloud-object-delete-adapters：S3 exact-target delete adapter、LocalStack parity 和真实删除保护
├── cleanup-scheduler-execution：基于 lock/history/signed plan 的自动清理执行
├── quota-enforcement-operations：quota 阻断/override 的 UI、审计和配置运维化
└── audit-runbook-release：审计 replay、runbook、rollback 和发布前验证脚本
```

### integration-control-plane · 真实集成控制面

- **职责**：集中定义真实外部动作的 capability flag、readiness gate、kill switch、配置摘要和 release gate；只判断是否允许进入真实执行，不执行具体 provider 调用。
- **承载的子 feature**：`integration-control-plane`。
- **触碰的现有代码 / 模块**：`app/core/config.py`、`app/services/health_service.py`、`app/domains/ops/recovery_actions.py`、`docs/api/health.md`、`docs/api/ops.md`。

### alert-delivery-providers · 真实告警投递

- **职责**：把 Phase 5 fake/local outbox delivery 扩展为 adapter-based real delivery；管理 destination allowlist、rate limit、dedupe、timeout/error 和 delivery history。
- **承载的子 feature**：`real-alert-delivery-adapter-contract`、`slack-webhook-delivery-pilot`。
- **触碰的现有代码 / 模块**：`app/domains/ops/alert_destinations.py`、`app/domains/ops/alert_delivery.py`、`app/domains/ops/router.py`、`frontend/src/pages/OpsDashboardPage.vue`。

### provider-cancellation-adapters · 真实 provider cancellation

- **职责**：先验证 provider 是否支持 cancellation，再用精确 provider operation id 执行真实 cancellation；保持 fake adapter parity、idempotency、timeout/error 和结构化审计。
- **承载的子 feature**：`provider-cancellation-semantics-verification`、`real-provider-cancellation-adapter`。
- **触碰的现有代码 / 模块**：`app/domains/ops/provider_cancellation.py`、`app/clients/mineru_client.py`、`app/domains/ops/recovery_actions.py`、`frontend/src/pages/OpsDashboardPage.vue`。

### cloud-object-delete-adapters · 真实 S3 删除

- **职责**：把 S3 fake deletion contract 推进到 LocalStack parity 和受控真实 `delete_object`；删除目标必须包含 exact bucket/key 和可选 version id。
- **承载的子 feature**：`s3-delete-localstack-contract`、`real-s3-delete-guarded-execution`。
- **触碰的现有代码 / 模块**：`app/domains/files/service.py`、`app/domains/files/cleanup_execution.py`、`app/domains/files/router.py`、`frontend/src/pages/FileRetentionPage.vue`。

### cleanup-scheduler-execution · 自动清理执行

- **职责**：在已有 manual scheduler dry-run、cleanup lock、durable history 和 signed cleanup plan 之上增加 disabled-by-default scheduler execute loop。
- **承载的子 feature**：`cleanup-scheduler-controlled-execute`。
- **触碰的现有代码 / 模块**：`app/domains/files/scheduled_cleanup.py`、`app/domains/files/cleanup_history.py`、`app/domains/files/cleanup_lock.py`、`app/domains/files/cleanup_execution.py`。

### quota-enforcement-operations · Quota enforcement 运维硬化

- **职责**：把已经接入 upload authorization 的 quota block / admin override 做成可观测、可回滚、可审计的 Admin 工作流；不再改变 quota 计算规则本身。
- **承载的子 feature**：`quota-enforcement-ops-hardening`。
- **触碰的现有代码 / 模块**：`app/domains/files/quota_policy.py`、`app/domains/files/router.py`、`frontend/src/pages/FileRetentionPage.vue`、`frontend/src/pages/AuditLogPage.vue`。

### audit-runbook-release · 审计、runbook 和发布门禁

- **职责**：统一真实集成执行证据、history 查询、audit replay、release check 和 rollback runbook；不替具体 provider adapter 执行外部调用。
- **承载的子 feature**：`real-integration-audit-replay`、`phase6-release-gate-runbook`。
- **触碰的现有代码 / 模块**：`app/domains/audit/*`、`scripts/ops/check_release.py`、`docs/dev/*`、`docs/api/*`。

## 4. 模块间接口契约 / 共享协议（架构层详设）

### 4.1 Real Integration Control Gate

**方向**：router / service → integration-control-plane
**形式**：函数调用 + settings + readiness JSON。

**契约**：

```python
RealIntegrationCapability = Literal[
    "alert_delivery",
    "provider_cancellation",
    "s3_delete",
    "cleanup_scheduler_execute",
    "quota_enforcement",
]

@dataclass(frozen=True, slots=True)
class RealIntegrationGate:
    capability: RealIntegrationCapability
    enabled: bool
    dry_run_only: bool
    kill_switch_active: bool
    secrets_configured: bool
    provider_configured: bool
    readiness_status: Literal["disabled", "dry_run", "ready", "blocked"]
    blocking_reasons: list[str]

def resolve_real_integration_gate(capability: RealIntegrationCapability, settings: Settings) -> RealIntegrationGate
```

**Settings 命名约束**：

```text
ops_alert_real_delivery_enabled=false
ops_provider_cancellation_real_enabled=false
files_s3_delete_real_enabled=false
files_cleanup_scheduler_execute_enabled=false
files_quota_policy_enabled=false
files_quota_policy_dry_run=true
```

**约束**：

- `enabled=false` 或 `kill_switch_active=true` 时，真实执行必须返回阻断结果，不得调用 provider。
- readiness 只返回 secret reference 是否配置，不返回 secret value。
- 每个真实执行 endpoint 必须在调用 adapter 前记录 gate snapshot 到 response 或 audit details。

### 4.2 Alert Delivery Provider Adapter

**方向**：alert-delivery-providers → external Slack/email/webhook provider
**形式**：Protocol + delivery result + HTTP API。

**HTTP 契约**：

```text
POST /api/v1/ops/alert-deliveries/send
Request:
{
  "alert_codes": ["stage_spool_failed_messages_present"],
  "destination_ids": ["ops-slack-primary"],
  "channel": "slack",
  "reason": "incident response",
  "confirmation": "SEND REAL OPS ALERTS",
  "dedupe_window_minutes": 60
}
Response: OpsAlertDeliveryResponse with action_mode="real_send"
错误：400 invalid_request, 403 role_forbidden, 409 conflict
```

**Adapter 契约**：

```python
@dataclass(frozen=True, slots=True)
class AlertDeliveryAttempt:
    delivery_id: str
    destination_id: str
    channel: Literal["slack", "email", "webhook"]
    alert_code: str
    title: str
    summary: str
    idempotency_key: str
    timeout_seconds: int
    secret_ref: str

@dataclass(frozen=True, slots=True)
class AlertDeliveryProviderResult:
    outcome: Literal["sent", "deduped", "skipped", "failed", "timed_out"]
    external_message_id: str | None
    error_code: str | None
    error_message: str | None
    provider_calls_executed: bool
    idempotency_key: str
    duration_ms: int | None

class AlertDeliveryProvider(Protocol):
    def send(self, attempt: AlertDeliveryAttempt) -> AlertDeliveryProviderResult: ...
```

**约束**：

- Adapter 不接收 secret value 以外的完整 settings；secret value 由 secret resolver 按 `secret_ref` 注入，不进入 result。
- `deduped` 不再发送外部请求。
- `failed` / `timed_out` 必须写 audit details，但不能写 provider response body。
- UI 必须显示 confirmation phrase 和 destination exact target。

### 4.3 Provider Cancellation Adapter

**方向**：provider-cancellation-adapters → MinerU / provider cancellation API
**形式**：Protocol + capability verification + HTTP API。

**前置语义验证输出**：

```yaml
provider: mineru
cancel_supported: true | false
operation_id_field: mineru_batch_id
idempotency_model: provider_idempotent | client_deduped | unsupported
terminal_states: [completed, failed, canceled]
timeout_seconds: 10
docs_reference: primary-provider-doc-or-runbook-entry
```

**HTTP 契约**：

```text
POST /api/v1/ops/provider-cancellations/real-cancel
Request:
{
  "target_type": "document_job",
  "target_id": "docjob_...",
  "provider": "mineru",
  "reason": "operator requested upstream cancel",
  "confirmation": "CANCEL REAL PROVIDER OPERATION",
  "dedupe_window_minutes": 60
}
Response: OpsProviderCancellationResponse with action_mode="real_cancel"
错误：400 invalid_request, 403 role_forbidden, 409 conflict
```

**Adapter 契约**：

```python
@dataclass(frozen=True, slots=True)
class ProviderCancellationRequest:
    provider: Literal["mineru"]
    target_type: Literal["document_job", "legacy_job"]
    target_id: str
    operation_id: str
    data_id: str | None
    idempotency_key: str
    timeout_seconds: int

@dataclass(frozen=True, slots=True)
class ProviderCancellationResult:
    outcome: Literal["provider_canceled", "already_terminal", "not_supported", "failed", "timed_out"]
    provider_operation_id: str
    provider_request_id: str | None
    error_code: str | None
    error_message: str | None
    provider_calls_executed: bool
    idempotency_key: str

class ProviderCancellationAdapter(Protocol):
    def cancel(self, request: ProviderCancellationRequest) -> ProviderCancellationResult: ...
```

**约束**：

- `provider_cancellation_semanitcs_verification` 未完成前，real endpoint 必须保持不可用。
- 真实 cancellation 不自动取消本地 job；本地 cancel 是独立动作，必须另有 reason/audit。
- 对 terminal job 返回 ineligible 或 already-terminal 语义，不发起 provider call。

### 4.4 Cloud Object Delete Adapter

**方向**：cloud-object-delete-adapters → S3-compatible object storage
**形式**：Protocol + cleanup/delete report field。

**Adapter 契约**：

```python
@dataclass(frozen=True, slots=True)
class ObjectDeleteRequest:
    storage_provider: Literal["s3"]
    bucket: str
    object_key: str
    version_id: str | None
    expected_etag: str | None
    idempotency_key: str
    timeout_seconds: int

@dataclass(frozen=True, slots=True)
class ObjectDeleteResult:
    outcome: Literal["deleted", "already_missing", "version_mismatch", "failed", "timed_out", "disabled"]
    bucket: str
    object_key: str
    version_id: str | None
    provider_request_id: str | None
    error_code: str | None
    error_message: str | None
    real_delete_executed: bool
    idempotency_key: str

class ObjectDeleteAdapter(Protocol):
    def delete_exact(self, request: ObjectDeleteRequest) -> ObjectDeleteResult: ...
```

**共享 response 字段**：

```json
{
  "s3_delete_contract": {
    "contract_version": "s3-delete-real-v1",
    "adapter_mode": "real",
    "bucket": "bucket",
    "object_key": "key",
    "version_id": "version-or-null",
    "target_exact": true,
    "outcome": "deleted",
    "safety": {
      "real_s3_delete_executed": true,
      "metadata_mutated": true,
      "audit_events_written": true
    }
  }
}
```

**约束**：

- `target_exact=false` 时必须阻断真实删除。
- cleanup-run signed plan hash 必须包含 bucket/key/version/etag/delete contract version。
- Real delete 成功后才能把 metadata 标记为 `deleted`。

### 4.5 Cleanup Scheduler Execute Policy

**方向**：cleanup-scheduler-execution → files cleanup services
**形式**：scheduler policy + run history state transitions。

**Policy 契约**：

```python
@dataclass(frozen=True, slots=True)
class CleanupSchedulerExecutePolicy:
    enabled: bool
    dry_run_only: bool
    max_files_per_run: int
    lock_ttl_seconds: int
    require_signed_plan: bool
    require_real_s3_delete_gate: bool
    reason_template: str
```

**Run state 约束**：

```text
dry_run -> previewed -> executed
dry_run -> failed
previewed -> failed
```

**约束**：

- scheduler loop 默认 `dry_run_only=true`。
- execute 需要 cleanup lock、signed plan、preview hash 和 policy snapshot。
- scheduler 不得绕过 per-file delete eligibility。
- 任何 lock conflict、signature mismatch、quota/reclaim mismatch 都必须记录 failed history 且不删除。

### 4.6 Real Integration Audit Details

**方向**：所有真实集成模块 → audit-runbook-release
**形式**：AuditEvent.details 共享结构。

**共享结构**：

```json
{
  "integration": {
    "capability": "alert_delivery",
    "adapter_mode": "real",
    "contract_version": "alert-delivery-real-v1",
    "gate": {
      "enabled": true,
      "dry_run_only": false,
      "readiness_status": "ready",
      "blocking_reasons": []
    },
    "idempotency_key": "stable-key",
    "timeout_seconds": 10,
    "outcome": "sent",
    "provider_calls_executed": true,
    "external_request_id": "safe-id-or-null",
    "error_code": null,
    "error_message": null
  },
  "safety": {
    "secret_values_exposed": false,
    "local_job_mutated": false,
    "delete_executed": false,
    "conversion_workflow_executed": false
  }
}
```

**约束**：

- `external_request_id` 只能是 provider 返回的非敏感 request/message id。
- 不记录 full webhook URL、Authorization header、provider response body、object path beyond bucket/key、local filesystem path、file bytes、prompt text 或 API token。
- CSV export 继续保留 compact `reason`；JSON/details export 才输出结构化 evidence。

## 5. 子 feature 清单

1. **integration-control-plane** — 为真实外部动作增加独立 feature flags、readiness gate、kill switch 和 registry/status 暴露。
   - 所属模块：integration-control-plane
   - 依赖：无
   - 状态：planned
   - 对应 feature：未启动
   - 备注：所有后续真实执行 feature 的前置。

2. **real-alert-delivery-adapter-contract** — 固定 alert delivery provider protocol、delivery result、history/audit details 和 fake-provider parity 测试。
   - 所属模块：alert-delivery-providers、audit-runbook-release
   - 依赖：`integration-control-plane`
   - 状态：planned
   - 对应 feature：未启动

3. **slack-webhook-delivery-pilot** — 在单一 Slack/webhook destination 上启用 exact alert_codes 的真实发送 pilot。
   - 所属模块：alert-delivery-providers
   - 依赖：`real-alert-delivery-adapter-contract`
   - 状态：planned
   - 对应 feature：未启动
   - 备注：最小闭环；完成后能端到端展示一个真实 Ops alert 被发送、审计、dedupe 和回放。

4. **provider-cancellation-semantics-verification** — 验证 MinerU/provider cancellation primary API、状态机、超时、幂等和失败语义，形成是否可实现的决定输入。
   - 所属模块：provider-cancellation-adapters
   - 依赖：`integration-control-plane`
   - 状态：planned
   - 对应 feature：未启动
   - 备注：如果 provider 不支持 cancel，后续 real adapter 条目应 drop，不得硬做。

5. **real-provider-cancellation-adapter** — 在 API 语义已验证后实现精确 provider operation 的真实 cancellation adapter、endpoint、audit 和 UI gating。
   - 所属模块：provider-cancellation-adapters、audit-runbook-release
   - 依赖：`provider-cancellation-semantics-verification`
   - 状态：planned
   - 对应 feature：未启动

6. **s3-delete-localstack-contract** — 用 LocalStack 或等价 fake provider 固定 real S3 delete adapter contract、version/etag/idempotency 和 cleanup preview hash。
   - 所属模块：cloud-object-delete-adapters
   - 依赖：`integration-control-plane`
   - 状态：planned
   - 对应 feature：未启动

7. **real-s3-delete-guarded-execution** — 在 exact target、signed plan、audit details 和 release gate 下启用真实 S3 object delete。
   - 所属模块：cloud-object-delete-adapters、cleanup-scheduler-execution
   - 依赖：`s3-delete-localstack-contract`
   - 状态：planned
   - 对应 feature：未启动

8. **cleanup-scheduler-controlled-execute** — 把 manual scheduler dry-run 推进到 disabled-by-default 自动 execute loop，复用 lock/history/signed plan/delete contract。
   - 所属模块：cleanup-scheduler-execution
   - 依赖：`real-s3-delete-guarded-execution`
   - 状态：planned
   - 对应 feature：未启动

9. **quota-enforcement-ops-hardening** — 为 quota block/admin override 增加 Admin UI、audit details 展示、配置 readiness、runbook 和 rollback 验证。
   - 所属模块：quota-enforcement-operations、audit-runbook-release
   - 依赖：`integration-control-plane`
   - 状态：planned
   - 对应 feature：未启动

10. **real-integration-audit-replay** — 统一真实 delivery/cancel/delete/scheduler/quota 的 audit details 查询、导出、UI 展示和 compliance replay。
    - 所属模块：audit-runbook-release
    - 依赖：`real-alert-delivery-adapter-contract`、`s3-delete-localstack-contract`、`quota-enforcement-ops-hardening`
    - 状态：planned
    - 对应 feature：未启动

11. **phase6-release-gate-runbook** — 把真实集成 smoke、fake/local parity、OpenAPI、frontend build、rollback 和 kill-switch 检查纳入 release gate/runbook。
    - 所属模块：audit-runbook-release、integration-control-plane
    - 依赖：`slack-webhook-delivery-pilot`、`real-provider-cancellation-adapter`、`real-s3-delete-guarded-execution`、`cleanup-scheduler-controlled-execute`、`real-integration-audit-replay`
    - 状态：planned
    - 对应 feature：未启动

**最小闭环**：第 3 条 `slack-webhook-delivery-pilot` 做完后，系统能在一个 exact alert code + exact destination 上完成真实外部 delivery，同时保留 gate snapshot、dedupe、audit details、delivery result 和 UI 可见状态。

## 6. 排期思路

先做 `integration-control-plane`，因为所有真实动作都需要独立开关、kill switch 和 readiness gate。随后选择告警 delivery 做最小闭环：它不会删除对象、不会改变 job 状态，风险低于 provider cancellation、S3 delete 和 scheduler execute，但足以验证 secret-ref、adapter、timeout/error、dedupe、audit 和 UI 的真实外部调用链路。

Provider cancellation 必须先做语义验证；本仓库当前只能证明 fake cancellation 和 adapter hardening，不能假设 MinerU 支持取消。S3 deletion 先走 LocalStack/fake parity，再进入真实删除。Scheduler execute 必须排在 real S3 delete 之后，否则自动化无法正确处理 S3 文件。Quota enforcement 已有后端阻断/override 基础，Phase 6 只补运维 UI、审计展示和回滚门禁。

## 7. 观察项

- Phase 5 acceptance closeout 中记录的 deferred work 已部分变化：provider cancellation adapter hardening 和 quota enforcement 后端阻断已完成，后续验收文档如需保持历史准确性不应改写旧结论，但新的 Phase 6 feature design 需要读取当前代码而不是旧 closeout。
- `backend-fastapi-service` architecture 的 last_reviewed 是 2026-06-03，尚未描述 Phase 5 Ops contracts、quota enforcement、cleanup run history/lock/signed plan 等现状；后续 Phase 6 子 feature acceptance 时应回写 architecture。
- 真实 provider cancellation 的可行性仍未知；如果 primary provider 文档或 API 不支持取消，应把 `real-provider-cancellation-adapter` 标记 dropped，并保留 fake/local audit 合同。
- 当前 release check 偏后端主链路与 OpenAPI，不覆盖外部 Slack/webhook、LocalStack/S3、scheduler loop 或 secret-ref resolution；`phase6-release-gate-runbook` 需要补齐。

## 8. 变更日志

- 2026-06-07：创建 Phase 6 real integration readiness roadmap；拆分控制面、真实告警投递、真实 provider cancellation、真实 S3 delete、scheduler execute、quota 运维硬化和审计/runbook release gate。
