---
doc_type: roadmap
slug: real-integration-readiness
status: completed
created: 2026-06-07
last_reviewed: 2026-06-08
tags: [phase6, operations, real-integration, alerts, provider-cancellation, s3, scheduler, quota]
related_requirements: [fastapi-backend-productization]
related_architecture: [backend-fastapi-service, conversion-flow]
---

# Phase 6 Real Integration Readiness

## 1. 背景

Phase 5 已把 Ops 高风险动作推进到 fake、dry-run、preview、signed plan、cleanup lock、structured audit details、quota preflight 和前端可视化控制。系统现在能证明目标选择、确认短语、dedupe、audit details、run history 和 dry-run history 的基础合同。

Phase 6 的目标不是一次性打开所有真实外部动作，而是把真实集成上线前的 readiness foundations 落地：控制面、readiness gate、kill switch、安全配置摘要、fake/local parity、timeout/error/idempotency 合同、结构化审计证据和 quota 运维硬化。

2026-06-08 closeout 决定：Phase 6 收口为 `real integration readiness foundations completed`。真实 Slack/webhook pilot、真实 S3 deletion、cleanup scheduler execute 不继续留在 Phase 6，转入 Phase 7 / 后续 controlled rollout 阶段；真实 provider cancellation 继续被 `unsupported_by_public_docs` 阻断，除非 provider 支持证据变化或有私有 provider 合同被批准。

## 2. 范围与明确不做

### 本 roadmap 覆盖

- 真实集成控制面：按能力分开的 feature flag、kill switch、readiness gate 和 blocked status。
- 真实 Ops alert delivery foundation：固定 provider contract、fake-send parity、timeout/error/idempotency/audit evidence；不执行 live send。
- Provider cancellation foundation：验证 MinerU/provider cancellation API 语义并记录 unsupported decision；不实现真实取消 adapter。
- S3 delete foundation：固定 fake/LocalStack parity contract、exact target metadata、version/etag/idempotency 和 blocked status；不执行真实删除。
- Cleanup scheduler execute foundation：保持 dry-run/history/lock/signed plan 基础，明确 execute 仍被 blocked。
- Quota enforcement 运维硬化：当前后端阻断/override 能力后的 UI、审计展示、配置检查和回滚口径。
- API docs、OpenAPI、Ops UI 和 focused tests 作为 readiness foundation release evidence。

### 明确不做

- 不在 roadmap 本身执行任何真实外部调用、删除、scheduler loop 或 provider cancellation。
- 不把真实 Slack/webhook pilot、真实 S3 deletion 或 cleanup scheduler execute 继续作为 Phase 6 范围；这些是 Phase 7 / 后续 controlled rollout 候选。
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
   - 状态：done
   - 对应 evidence：`.trellis/tasks/archive/2026-06/06-07-phase6-integration-control-plane/`
   - 备注：Phase 6 foundation 最小闭环；Admin-only read-only capability status 已落地，真实外部/破坏性执行仍默认 blocked。

2. **real-alert-delivery-adapter-contract** — 固定 alert delivery provider protocol、delivery result、history/audit details 和 fake-provider parity 测试。
   - 所属模块：alert-delivery-providers、audit-runbook-release
   - 依赖：`integration-control-plane`
   - 状态：done
   - 对应 evidence：`.trellis/tasks/archive/2026-06/06-07-phase6-real-alert-delivery-adapter-contract/`
   - 备注：只接受 adapter contract 和 fake-send parity；live Slack/email/webhook send 不属于 Phase 6。

3. **slack-webhook-delivery-pilot** — 在单一 Slack/webhook destination 上启用 exact alert_codes 的真实发送 pilot。
   - 所属模块：alert-delivery-providers
   - 依赖：`real-alert-delivery-adapter-contract`
   - 状态：dropped
   - 对应 evidence：未启动
   - 备注：从 Phase 6 移到 Phase 7 / controlled rollout；能力未放弃，但必须另起真实外部上线任务并获得测试 destination、secret-ref、allowlist、rate limit、confirmation 和 rollback 批准。

4. **provider-cancellation-semantics-verification** — 验证 MinerU/provider cancellation primary API、状态机、超时、幂等和失败语义，形成是否可实现的决定输入。
   - 所属模块：provider-cancellation-adapters
   - 依赖：`integration-control-plane`
   - 状态：done
   - 对应 evidence：`.trellis/tasks/archive/2026-06/06-07-phase6-provider-cancellation-semantics-verification/`
   - 备注：验收决定为 `unsupported_by_public_docs`；真实 provider cancellation 继续 blocked。

5. **real-provider-cancellation-adapter** — 在 API 语义已验证后实现精确 provider operation 的真实 cancellation adapter、endpoint、audit 和 UI gating。
   - 所属模块：provider-cancellation-adapters、audit-runbook-release
   - 依赖：`provider-cancellation-semantics-verification`
   - 状态：dropped
   - 对应 evidence：未启动
   - 备注：从 Phase 6 移出并保持 blocked；只有 primary provider evidence 变化或私有 provider 合同被批准后，才能作为后续 controlled rollout 候选重新建项。

6. **s3-delete-localstack-contract** — 用 LocalStack 或等价 fake provider 固定 real S3 delete adapter contract、version/etag/idempotency 和 cleanup preview hash。
   - 所属模块：cloud-object-delete-adapters
   - 依赖：`integration-control-plane`
   - 状态：done
   - 对应 evidence：`.trellis/tasks/archive/2026-06/06-07-phase6-s3-delete-localstack-contract/`
   - 备注：只接受 fake/LocalStack parity contract、exact-target metadata 和 blocked status；真实 S3 delete 不属于 Phase 6。

7. **real-s3-delete-guarded-execution** — 在 exact target、signed plan、audit details 和 release gate 下启用真实 S3 object delete。
   - 所属模块：cloud-object-delete-adapters、cleanup-scheduler-execution
   - 依赖：`s3-delete-localstack-contract`
   - 状态：dropped
   - 对应 evidence：未启动
   - 备注：从 Phase 6 移到 Phase 7 / controlled rollout；这是破坏性执行，必须另起明确批准的真实删除上线任务。

8. **cleanup-scheduler-controlled-execute** — 把 manual scheduler dry-run 推进到 disabled-by-default 自动 execute loop，复用 lock/history/signed plan/delete contract。
   - 所属模块：cleanup-scheduler-execution
   - 依赖：`real-s3-delete-guarded-execution`
   - 状态：dropped
   - 对应 evidence：未启动
   - 备注：从 Phase 6 移到 Phase 7+ / controlled rollout；必须排在 guarded real S3 delete 之后，不能成为第一个真实破坏性执行入口。

9. **quota-enforcement-ops-hardening** — 为 quota block/admin override 增加 Admin UI、audit details 展示、配置 readiness、runbook 和 rollback 验证。
   - 所属模块：quota-enforcement-operations、audit-runbook-release
   - 依赖：`integration-control-plane`
   - 状态：done
   - 对应 evidence：`.trellis/tasks/archive/2026-06/06-07-phase6-quota-enforcement-ops-hardening/`
   - 备注：current ready-state upload blocking 和 Admin override 已接受为内部 enforcement；Phase 6 完成的是 ops hardening、rollback visibility 和 audit replay。

10. **real-integration-audit-replay** — 统一真实 delivery/cancel/delete/scheduler/quota 的 audit details 查询、导出、UI 展示和 compliance replay。
    - 所属模块：audit-runbook-release
    - 依赖：`real-alert-delivery-adapter-contract`、`s3-delete-localstack-contract`、`quota-enforcement-ops-hardening`
    - 状态：dropped
    - 对应 evidence：未启动
    - 备注：从 Phase 6 移到后续 controlled rollout/release evidence 阶段；真实 execution pilot 选定后再按实际能力建项。

11. **phase6-release-gate-runbook** — 把真实集成 smoke、fake/local parity、OpenAPI、frontend build、rollback 和 kill-switch 检查纳入 release gate/runbook。
    - 所属模块：audit-runbook-release、integration-control-plane
    - 依赖：`slack-webhook-delivery-pilot`、`real-provider-cancellation-adapter`、`real-s3-delete-guarded-execution`、`cleanup-scheduler-controlled-execute`、`real-integration-audit-replay`
    - 状态：dropped
    - 对应 evidence：未启动
    - 备注：Phase 6 closeout 已用 focused tests、OpenAPI currentness、frontend build 和 `git diff --check` 验收 foundation；真实上线 release gate/runbook 移到 Phase 7 / controlled rollout。

**最小闭环**：`integration-control-plane` 是 Phase 6 foundation 最小闭环。真实 Slack/webhook delivery 不再作为 Phase 6 最小闭环；它是 Phase 7 / controlled rollout 候选。

## 6. 排期结果

Phase 6 实际完成顺序为：

1. `integration-control-plane`
2. `quota-enforcement-ops-hardening`
3. `real-alert-delivery-adapter-contract`
4. `provider-cancellation-semantics-verification`
5. `s3-delete-localstack-contract`

Phase 6 closeout 决定不再继续推进真实执行。后续阶段建议顺序：

1. 如果要选择最低风险真实外部调用，先开 Phase 7 `slack-webhook-delivery-pilot`，但必须先批准真实测试 destination、secret-ref、allowlist、rate limit、confirmation phrase 和 rollback。
2. `real-s3-delete-guarded-execution` 单独作为破坏性 controlled rollout，不与 Slack/webhook pilot 合并。
3. `cleanup-scheduler-controlled-execute` 必须排在 guarded real S3 delete 之后，并保持 disabled-by-default。
4. `real-provider-cancellation-adapter` 只有在 provider 支持证据变化或私有合同被批准后才重新进入计划。

## 7. 观察项

- Phase 6 已从“打开真实执行”收窄为“真实集成 readiness foundations completed”。旧的 Phase 6 子项中仍涉及真实执行的部分已经在本 roadmap 标记 `dropped`，语义是移出 Phase 6，不代表能力永久放弃。
- `backend-fastapi-service` architecture 的 last_reviewed 是 2026-06-03，尚未描述 Phase 5/6 Ops contracts、quota enforcement、cleanup run history/lock/signed plan、integration control plane、alert delivery contract、provider semantics report 和 S3 delete contract 等现状；后续应由 acceptance/architecture 流程回写。
- 真实 provider cancellation 当前被 `unsupported_by_public_docs` 阻断；不要把 fake cancellation hardening 解读为真实 provider cancellation readiness。
- 当前 release check 偏后端主链路与 OpenAPI，不覆盖真实 Slack/webhook、真实 S3、scheduler execute 或 secret-ref resolution；这些检查属于 Phase 7 / controlled rollout。

## 8. Phase 7 controlled rollout status

2026-06-08 状态快照：

| Task | Status | Execution Permission |
| --- | --- | --- |
| `phase7-slack-webhook-delivery-pilot` | no-live implementation accepted | No live send approved |
| `phase7-slack-webhook-live-smoke-preflight` | accepted; not archived | Preflight only |
| `phase7-slack-webhook-live-smoke-approval` | prepared; blocked | Approval discussion only |
| `phase7-slack-webhook-live-smoke-execution` | prepared; blocked | Requires separate explicit approval for exactly one send |
| `phase7-slack-webhook-live-smoke-closeout` | prepared; blocked | Requires accepted live smoke evidence |
| `phase7-real-s3-delete-guarded-rollout-planning` | planning scaffold prepared; target blocked | Planning only; exact target values missing |
| `phase7-real-s3-delete-guarded-execution` | prepared; blocked | Requires destructive rollout planning acceptance and explicit approval |
| `phase7-cleanup-scheduler-controlled-execute-planning` | prepared; blocked | Requires accepted real S3 delete evidence |
| `phase7-provider-cancellation-evidence-watch` | prepared; blocked | Requires provider evidence change or private provider contract |
| `phase7-controlled-rollout-status-sync` | prepared | Documentation/status only |

Phase 7 当前没有任何 task 授权真实 Slack/webhook 发送、真实 provider cancellation、真实 S3 delete、LocalStack delete、cleanup scheduler execute 或转换主流程。

## 9. 变更日志

- 2026-06-07：创建 Phase 6 real integration readiness roadmap；拆分控制面、真实告警投递、真实 provider cancellation、真实 S3 delete、scheduler execute、quota 运维硬化和审计/runbook release gate。
- 2026-06-08：按 Trellis Phase 6 closeout 更新 roadmap 状态；Phase 6 收口为 readiness foundations completed，真实 Slack/webhook pilot、真实 S3 delete、cleanup scheduler execute 和真实上线 release gate 移到 Phase 7 / controlled rollout。
- 2026-06-08：创建 Phase 7 controlled rollout task queue；Slack live-smoke approval/execution/closeout、S3 destructive rollout、scheduler execute 和 provider cancellation 均保持 blocked，未执行真实外部或破坏性动作。
