---
doc_type: audit-finding
audit: 2026-06-09-phase9-stabilization
finding_id: "maintainability-03"
nature: maintainability
severity: P2
confidence: high
suggested_action: cs-refactor
status: open
---

# Finding 03：Ops Integration 测试集中在超大 Backend 测试文件中

## 速答

`tests/test_fastapi_jobs_backend.py` 同时承载 jobs、files、ops、document jobs 等大量场景；Phase 7/8 相关 ops integration 测试分散在一个 13k+ 行文件里，后续修改 live rollout gate 时定位和选择性回归成本偏高。

## 关键证据

- `tests/test_fastapi_jobs_backend.py` — `wc -l` 显示该文件有 13,715 行。
- `tests/test_fastapi_jobs_backend.py:2265` 到 `tests/test_fastapi_jobs_backend.py:2645` — Slack real alert delivery preview / execution / dedupe / rate-limit 测试集中在大文件中。
- `tests/test_fastapi_jobs_backend.py:3004` 到 `tests/test_fastapi_jobs_backend.py:3230` — provider cancellation semantics、S3 adapter contract、integration capabilities 测试也在同一个文件中。

## 影响

这不是行为 bug。风险是 Phase 9 后续如果修 Slack live readiness 或 idempotency，开发者需要在超大测试文件中定位相关 setup/helper，容易扩大改动范围，也不利于只跑 ops focused tests。

## 修复方向

后续可把 ops integration control plane、real alert delivery、provider cancellation 和 S3 delete contract 测试拆到独立测试文件，并保留现有 helper 复用。

## 建议动作

`cs-refactor`，因为这是行为保持的测试结构整理；不应和 live rollout 修复混在同一个任务里。
