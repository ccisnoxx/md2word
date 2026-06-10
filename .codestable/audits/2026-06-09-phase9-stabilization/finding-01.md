---
doc_type: audit-finding
audit: 2026-06-09-phase9-stabilization
finding_id: "bug-01"
nature: bug
severity: P1
confidence: high
suggested_action: cs-issue
status: open
---

# Finding 01：Control Plane 可能过早报告 Slack Live-Send Ready

## 速答

`alert_delivery` capability 的 `ready` 状态只看 feature flag、destination 配置和 dry-run/kill-switch，没有验证 `OPS_SLACK_WEBHOOK_URL` 是否在运行时可解析；重新开启 Slack live rollout 时，operator 可能把 control plane 的 `ready` 误读为真实发送已完全就绪。

## 关键证据

- `app/domains/ops/integration_control.py:147` 到 `app/domains/ops/integration_control.py:155` — `configured` 只来自 `pilot_destination_ready`，blocking reasons 只扩展 destination summary，没有 secret resolver 或 secret presence gate。
- `app/domains/ops/integration_control.py:165` 到 `app/domains/ops/integration_control.py:180` — `safe_config` 暴露 `pilot_secret_ref` 和 `secret_values_exposed=false`，但没有 `secret_ref_configured` 或等价状态。
- `app/domains/ops/real_alert_delivery.py:468` 到 `app/domains/ops/real_alert_delivery.py:471` — 真实 `real_send` 执行时才解析 secret，未解析时追加 `secret_ref_unresolved`。
- `tests/test_fastapi_jobs_backend.py:3289` 到 `tests/test_fastapi_jobs_backend.py:3338` — 测试明确接受 control plane 报告 `status=ready`，且 provider / secret resolver 没有被调用。
- `.codestable/architecture/backend-fastapi-service.md:231` 到 `.codestable/architecture/backend-fastapi-service.md:234` — 当前 Phase 7 事实要求 `OPS_SLACK_WEBHOOK_URL` 未注入 active runtime env 时 live send deferred。

## 影响

当前 real rollout 已 deferred，因此不会立即触发 live send。但如果之后只看 `/api/v1/ops/integration-capabilities` 的 `alert_delivery.ready=true` 来批准 live smoke，会漏掉 secret 未配置这一关键 runtime gate，导致执行阶段才 blocked，或者让上线前检查语义变得不可信。

## 修复方向

在 control plane 中区分 `ready_for_preview` 与 `ready_for_live_execution`，或增加不暴露 secret value 的 secret presence gate；在无法安全检查 secret presence 时，`alert_delivery` 不应报告完整 `ready`。

## 建议动作

`cs-issue`，因为这是重新开启 Slack live rollout 前的 readiness 语义 bug，需要最小代码修复和测试更新。
