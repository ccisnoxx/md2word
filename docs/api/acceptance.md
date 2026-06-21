---
doc_type: lib-api-ref
entry: acceptance
category: endpoint
status: current
source_files:
  - app/api/v1/router.py
  - app/domains/acceptance/router.py
  - app/domains/acceptance/schemas.py
  - app/domains/acceptance/service.py
  - app/domains/acceptance/repository.py
  - app/domains/acceptance/defaults.py
summary: Acceptance API 提供 Admin-only P0/P1/P2 验收证据摘要和复核记录。
tags: [acceptance, ops, api, admin]
last_reviewed: 2026-06-21
---

## 概述

Acceptance API 挂在 `/api/v1/acceptance` 下，为内部 admin 提供小型验收证据索引。
它只保存摘要、报告路径、阻断项、告警和复核结论；不保存 PDF、Word、二进制 artifact、JWT、secret、客户全文、完整 prompt 或 provider 响应。

运行时仓库为空时，服务会写入三条非通过的 starter summaries，分别指向当前 P0 Golden Sample、P1 translation 和 P2 online gate 证据来源。它们用于引导复核，不代表最新验收运行通过。

## API 参考

### `GET /api/v1/acceptance/runs`

- 用途：列出验收运行摘要。
- 鉴权：Admin Bearer JWT。
- Query：
  - `tier`: `P0`、`P1` 或 `P2`
  - `status`: `passed`、`failed` 或 `unknown`
  - `limit`: `1..100`，默认 `50`
- 响应：

```json
{
  "items": [
    {
      "id": "acceptance_p0_golden_sample_current",
      "title": "P0 Golden Sample canonical suite",
      "tier": "P0",
      "status": "failed",
      "environment": "hostdzire",
      "source": "manual_summary:golden_sample_acceptance_report",
      "report_path_or_url": "docs/testing/pdf-to-word-golden-sample-acceptance-report.md",
      "started_at": null,
      "finished_at": null,
      "summary": "Current canonical-suite report records the main chain as exercised, but P0 manual Word quality is not approved.",
      "blockers": ["p0_manual_quality_not_approved"],
      "warnings": ["starter_summary_replace_with_latest_run_report"],
      "reviewer": null,
      "decision": null,
      "reviewed_at": null,
      "review_note": null,
      "updated_at": "2026-06-21T00:00:00Z"
    }
  ],
  "total": 1
}
```

### `GET /api/v1/acceptance/runs/{run_id}`

- 用途：读取单条验收运行详情。
- 鉴权：Admin Bearer JWT。
- 缺失时返回 `404 not_found`。

### `POST /api/v1/acceptance/runs/{run_id}/review`

- 用途：记录 admin 复核结论。
- 鉴权：Admin Bearer JWT。
- 请求体：

```json
{
  "decision": "needs_changes",
  "review_note": "P1 formal run 和 P2 online gate 证据仍需补齐。"
}
```

- `decision`: `approved`、`rejected` 或 `needs_changes`
- 成功动作写入 `acceptance_run.review` audit event。
- 复核只更新 `reviewer`、`decision`、`reviewed_at` 和 `review_note`，不会把 `unknown` 或 `failed` 的运行状态改成 `passed`。

## 运营注意事项

- Acceptance Center 是证据索引和签字面，不执行转换、翻译、清理、provider 调用或真实发布动作。
- starter summaries 必须被最新脚本报告或人工导入摘要替换后，才适合作为发布验收证据。
- `approved` 表示 reviewer 对该条摘要负责，不等于所有 P0/P1/P2 gate 自动通过；页面仍会展示原始 `status`、`blockers` 和 `warnings`。
