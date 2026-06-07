# Phase 6 Integration Control Plane Design

## Decision

Implement the first Phase 6 control plane as a read-only Ops capability status API plus frontend display. The API reports gates; it does not execute real integrations.

## Backend Shape

- Add `app/domains/ops/integration_control.py`.
- Add response schemas in `app/domains/ops/schemas.py`.
- Add `GET /api/v1/ops/integration-capabilities` in `app/domains/ops/router.py`.
- Add disabled-by-default settings in `app/core/config.py`.

## Capability Rules

- `alert_delivery`: real Slack/email/webhook delivery, default disabled and dry-run-only.
- `provider_cancellation`: real provider cancellation, default disabled and dry-run-only.
- `s3_deletion`: real S3 deletion, default disabled and dry-run-only.
- `cleanup_scheduler_execute`: autonomous scheduler execution, default disabled and dry-run-only.
- `quota_enforcement`: current upload quota enforcement remains controlled by existing quota settings; default remains disabled/dry-run.

## Safety

The control plane response contains only boolean/string/int safe summaries. It never returns secret values and does not call external systems or mutate state.

## Frontend

Add a compact panel to `frontend/src/pages/OpsDashboardPage.vue` and an API wrapper/type contract. The UI is display-only.
