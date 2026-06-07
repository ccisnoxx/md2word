# Phase 5 alert destination config dry run design

## Boundary

This task adds a configuration dry-run contract. It does not send notifications and does not add a real Slack/email/webhook client.

Excluded:

- real Slack delivery.
- real email delivery.
- real webhook delivery.
- retries, delivery history tables, scheduler, background workers, provider calls, S3 deletion, pdf-mineru parsing, translation, Word generation.

## Configuration

Add `Settings.ops_alert_destinations_json`.

Default:

```text
[]
```

Configured value is a JSON array:

```json
[
  {
    "destination_id": "ops-slack-primary",
    "channel": "slack",
    "enabled": false,
    "secret_ref": "OPS_SLACK_WEBHOOK_URL",
    "target_label": "#ops-alerts",
    "allowlist": ["stage_spool_failed_messages_present"],
    "rate_limit_per_hour": 30,
    "dedupe_window_minutes": 60
  }
]
```

Only `secret_ref` is stored and returned. Secret material is not read from the config JSON and is not returned.

## API Contract

Add:

```text
POST /api/v1/ops/alert-destinations/dry-run
```

Request:

```json
{
  "alert_codes": ["stage_spool_failed_messages_present"],
  "destination_ids": ["ops-slack-primary"]
}
```

Both lists are optional:

- no `destination_ids` means dry-run all configured destinations.
- no `alert_codes` means config-only dry-run.
- when `alert_codes` is present, codes must be exact, non-blank, unique, and capped at the existing alert delivery batch limit.

Response:

```json
{
  "generated_at": "2026-06-07T00:00:00+00:00",
  "action_mode": "config_dry_run",
  "requested_alert_codes": ["stage_spool_failed_messages_present"],
  "requested_destination_ids": ["ops-slack-primary"],
  "configured_count": 1,
  "selected_count": 1,
  "config_errors": [],
  "destinations": [
    {
      "destination_id": "ops-slack-primary",
      "channel": "slack",
      "enabled": false,
      "secret_ref": "OPS_SLACK_WEBHOOK_URL",
      "secret_ref_present": true,
      "target_label": "#ops-alerts",
      "allowlist": ["stage_spool_failed_messages_present"],
      "rate_limit_per_hour": 30,
      "dedupe_window_minutes": 60,
      "status": "disabled",
      "missing_gates": ["destination_disabled", "real_delivery_not_implemented"],
      "matched_alert_codes": ["stage_spool_failed_messages_present"],
      "blocked_alert_codes": []
    }
  ],
  "safety": {
    "read_only": true,
    "external_delivery_executed": false,
    "provider_calls_executed": false,
    "cleanup_executed": false,
    "delete_executed": false,
    "conversion_workflow_executed": false,
    "audit_events_written": false,
    "secret_values_exposed": false
  }
}
```

## Placement

- `app/core/config.py`
  - add `ops_alert_destinations_json`.
- `app/domains/ops/alert_destinations.py`
  - parse config.
  - validate destination definitions.
  - build dry-run report.
- `app/domains/ops/schemas.py`
  - request/response contracts.
- `app/domains/ops/router.py`
  - endpoint and mapper.
- `frontend/src/api/types.ts`
  - TS contracts.
- `frontend/src/api/opsAlertDestinations.ts`
  - API wrapper.
- `frontend/src/pages/OpsDashboardPage.vue`
  - read-only dry-run panel.
- `docs/api/ops.md` and `docs/api/openapi.json`.
- `tests/test_fastapi_jobs_backend.py`.

## Safety

- Endpoint requires Admin.
- Endpoint is read-only and writes no audit.
- It validates config and alert-code matching only.
- Real delivery remains unavailable even if config says `enabled=true`; response always includes `real_delivery_not_implemented`.
- It returns only secret reference names, never secret values.
- Invalid JSON or invalid items appear in `config_errors` and do not cause external side effects.

## Compatibility

- Additive setting with safe default.
- Additive API endpoint.
- Existing local fake outbox endpoints remain unchanged.
- Existing recovery action registry still marks real external delivery as a known gap.

## Risks

- Operators may interpret `enabled=true` as live delivery. The response and UI must state that real delivery is not implemented.
- If a destination allowlist is empty, alert-code dry-run should block all requested codes rather than treating empty as wildcard.
