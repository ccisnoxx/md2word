# Ops alerting and recovery readiness design

## Existing Context

- `HealthService.build_dependency_checks()` already exposes readiness blockers/warnings, stage message counts, stale running observations, and runtime metadata.
- `HealthService.build_metrics_response()` already exposes job status counts, stage message counts, resource counts, and audit event totals.
- `OpsDashboardPage.vue` currently derives alerts in the frontend from health readiness, metrics, and document job list samples.
- The current dashboard is read-only and must stay read-only.

## API Contract

Add:

```text
GET /api/v1/health/ops-alerts
```

Authentication:

- Bearer JWT, Admin only.

Response:

```json
{
  "status": "needs_attention",
  "app_name": "md2word",
  "generated_at": "2026-06-06T00:00:00+00:00",
  "summary": {
    "readiness_blockers": 0,
    "readiness_warnings": 2,
    "stage_failed_messages": 1,
    "stage_stale_running_messages": 1,
    "stage_replayable_messages": 2,
    "failed_jobs": 3,
    "running_jobs": 1
  },
  "alerts": [
    {
      "code": "stage_spool_failed_messages_present",
      "severity": "critical",
      "source": "stage_spool",
      "title": "Failed stage messages",
      "description": "failed stage message 不会自动 replay...",
      "count": 1,
      "suggested_route": "/jobs?status=failed&sort=updated_at_desc",
      "suggested_action": "Open failed job details..."
    }
  ],
  "safety": {
    "read_only": true,
    "writes_performed": false,
    "recovery_actions_executed": false,
    "provider_calls_executed": false,
    "notification_delivery_executed": false
  }
}
```

Status rules:

- `needs_attention` if readiness blockers, failed stage messages, or stale running messages exist.
- `watch` if readiness warnings, replayable messages, failed jobs, or running jobs exist.
- `ok` otherwise.

## Alert Sources

- `readiness`: readiness blockers and warnings.
- `stage_spool`: failed, stale running, and replayable stage messages.
- `jobs`: failed and running document job counts.

## Frontend

- Add `healthApi.getOpsAlerts()`.
- Add TypeScript contracts for `HealthOpsAlertsResponse` and alert rows.
- Make `OpsDashboardPage.vue` render backend-provided alert list and status where available.
- Keep existing readiness/metrics/job sample panels.
- Keep existing read-only warning copy.

## Safety

- No mutation endpoint is added.
- No automatic retry/cancel/archive/recover/cleanup is called.
- No provider cancellation or notification delivery is called.
- No audit event is written for status reads.
- Suggested routes are plain internal UI routes, not action URLs.

## Risks

- Some current frontend-derived wording will move to backend strings; tests must assert contract fields, not exact full UI rendering.
- Health endpoints currently include public ready/metrics routes. This task adds one Admin-only endpoint without changing existing public route behavior.
