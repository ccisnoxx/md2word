---
doc_type: audit-finding
audit: 2026-06-09-phase9-stabilization
finding_id: "bug-02"
nature: bug
severity: P1
confidence: medium
suggested_action: cs-issue
status: open
---

# Finding 02：Slack Provider 调用先于 Durable Audit

## 速答

Slack real-send 的外部 provider 调用发生在 audit 持久化之前；如果 provider 调用成功但后续 audit 写入失败，dedupe/rate-limit 依赖的 evidence 会缺失，后续重试可能破坏 exactly-one live smoke 语义。

## 关键证据

- `app/domains/ops/real_alert_delivery.py:397` 到 `app/domains/ops/real_alert_delivery.py:431` — rate-limit 通过后直接调用 `self.provider.send(...)`，随后只返回 report。
- `app/domains/ops/router.py:182` 到 `app/domains/ops/router.py:204` — router 在 `service.real_send(...)` 返回后才调用 `runtime.audit_service.record(...)` 写 audit。
- `app/domains/ops/real_alert_delivery.py:573` 到 `app/domains/ops/real_alert_delivery.py:607` — dedupe 和 rate-limit 都只读取已有 real delivery audit events。
- `tests/test_fastapi_jobs_backend.py:2496` 到 `tests/test_fastapi_jobs_backend.py:2578` — 成功路径通过第一条 audit 后，第二次请求才 dedupe；测试没有覆盖 provider 已发送但 audit 写失败的路径。

## 影响

触发条件是 audit repository 在 provider call 之后失败，或进程在发送成功与 audit 持久化之间崩溃。当前 live rollout deferred，所以不是立即生产事故；但 exactly-one Slack live smoke 和 rate-limit 都依赖 audit evidence，该窗口在未来 live rollout 中会成为重复发送风险。

## 修复方向

在 provider call 前写入 durable pending attempt / idempotency record，或引入 delivery attempt store；provider 返回后再补 outcome。dedupe/rate-limit 应同时识别 pending/sent/failed attempt，而不是只依赖 post-send audit。

## 建议动作

`cs-issue`，因为这是真实外部发送安全语义问题；应在任何 renewed Slack live-smoke approval 之前修复。
