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
summary: Acceptance API 提供 Admin-only P0/P1/P2 验收证据摘要、最新状态派生和复核记录。
tags: [acceptance, ops, api, admin]
last_reviewed: 2026-06-21
---

## 概述

Acceptance API 挂在 `/api/v1/acceptance` 下，为内部 admin 提供小型验收证据索引。
它只保存摘要、报告路径、阻断项、告警和复核结论；不保存 PDF、Word、二进制 artifact、JWT、secret、客户全文、完整 prompt 或 provider 响应。

运行时仓库为空时，服务会写入三条 starter summaries，分别指向 P0 Golden Sample、P1 translation 和 P2 online gate 证据来源。P0 starter summary 只是 2026-06-17 hostdzire admin signoff 的历史引导摘要；P1/P2 仍是 `unknown` 且带 blocker。starter summaries 不能直接当成下一次发布证据，发布前必须被最新脚本报告或人工导入摘要替换。

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
      "status": "passed",
      "environment": "hostdzire",
      "source": "manual_summary:golden_sample_acceptance_report",
      "report_path_or_url": "docs/testing/pdf-to-word-golden-sample-acceptance-report.md",
      "started_at": null,
      "finished_at": null,
      "summary": "Historical starter summary: the Golden Sample report records the 2026-06-17 hostdzire admin signoff. Replace this starter summary with the latest run report before using Acceptance Center as release evidence.",
      "blockers": [],
      "warnings": [
        "starter_summary_historical_p0_signoff",
        "starter_summary_replace_with_latest_run_report_before_release"
      ],
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

### `POST /api/v1/acceptance/runs`

- 用途：由 admin 登记或替换一条验收运行摘要，把最新脚本报告或人工整理的验收结论写入 Acceptance Center。
- 鉴权：Admin Bearer JWT。
- 创建新 `id` 返回 `201`；覆盖已有 `id` 返回 `200`。
- 同 `id` 覆盖表示新的验收证据替换旧证据，服务会清空旧 `reviewer`、`decision`、`reviewed_at` 和 `review_note`，需要 admin 重新复核。
- 成功动作写入 `acceptance_run.upsert` audit event。
- 请求体：

```json
{
  "id": "acceptance_p1_translation_current",
  "title": "P1 Translation Formal Run",
  "tier": "P1",
  "status": "unknown",
  "environment": "hostdzire",
  "source": "manual_import:p1_translation",
  "report_path_or_url": "tests/tmp/p1_translation_runs/run-1/report.md",
  "started_at": "2026-06-21T01:00:00Z",
  "finished_at": "2026-06-21T01:08:00Z",
  "summary": "等待人工签字。",
  "blockers": ["p1_manual_signoff_pending"],
  "warnings": ["report_pending"]
}
```

- `tier`: `P0`、`P1` 或 `P2`
- `status`: `passed`、`failed` 或 `unknown`
- `finished_at` 不能早于 `started_at`。
- `blockers` 和 `warnings` 会去除空白项；有 blocker 或 failed 的最新证据会让 `latest-summary` 进入阻断态。

### `GET /api/v1/acceptance/runs/{run_id}`

- 用途：读取单条验收运行详情。
- 鉴权：Admin Bearer JWT。
- 缺失时返回 `404 not_found`。

### `GET /api/v1/acceptance/runs/latest-summary`

- 用途：从当前 runs 派生 P0/P1/P2 最新验收状态，用于验收中心概览和发布签字判断。
- 鉴权：Admin Bearer JWT。
- 该接口不写入 metadata，不读取原始 PDF、Word、LLM prompt/response 或 provider payload。
- `overall_status`：
  - `accepted`：P0/P1/P2 最新证据均存在，且没有 blocker、failed、unknown 或 warning。
  - `blocked`：至少一个层级的最新证据失败或带 blocker。
  - `incomplete`：缺少 P0/P1/P2 任一层级证据。
  - `needs_attention`：没有 blocker，但存在 warning 或 unknown。
- 响应示例：

```json
{
  "overall_status": "incomplete",
  "missing_tiers": ["P2"],
  "blocker_count": 1,
  "warning_count": 2,
  "latest_reviewed_run": null,
  "tiers": [
    {
      "tier": "P0",
      "run": {
        "id": "acceptance_p0_golden_sample_current",
        "title": "P0 Golden Sample canonical suite",
        "tier": "P0",
        "status": "passed",
        "environment": "hostdzire",
        "source": "manual_summary:golden_sample_acceptance_report",
        "report_path_or_url": "docs/testing/pdf-to-word-golden-sample-acceptance-report.md",
        "started_at": null,
        "finished_at": null,
        "summary": "Historical starter summary: the Golden Sample report records the 2026-06-17 hostdzire admin signoff. Replace this starter summary with the latest run report before using Acceptance Center as release evidence.",
        "blockers": [],
        "warnings": [
          "starter_summary_historical_p0_signoff",
          "starter_summary_replace_with_latest_run_report_before_release"
        ],
        "reviewer": null,
        "decision": null,
        "reviewed_at": null,
        "review_note": null,
        "updated_at": "2026-06-21T00:00:00Z"
      },
      "missing": false,
      "risk_level": "warning",
      "blockers": [],
      "warnings": [
        "starter_summary_historical_p0_signoff",
        "starter_summary_replace_with_latest_run_report_before_release"
      ]
    }
  ],
  "generated_at": "2026-06-21T00:00:00Z"
}
```

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
- starter summaries 是引导数据；必须被最新脚本报告或人工导入摘要替换后，才适合作为下一次发布验收证据。
- `approved` 表示 reviewer 对该条摘要负责，不等于所有 P0/P1/P2 gate 自动通过；页面仍会展示原始 `status`、`blockers` 和 `warnings`。
- `latest-summary` 是派生视图，不是第二个持久化真源；实际证据仍以 `runs` 记录及其报告路径为准。
- `latest-summary` 每个 tier 的最新证据按 `finished_at`、`started_at`、`updated_at` 顺序判断；复核动作更新 review metadata，但不改变证据运行的新旧顺序。
