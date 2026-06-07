# Phase 5 alert delivery frontend controls design

## Scope

Frontend-only slice.

Files to change:

- `frontend/src/api/types.ts`
- `frontend/src/api/opsAlertDeliveries.ts`
- `frontend/src/pages/OpsDashboardPage.vue`

No backend code, OpenAPI schema, persistence adapter, config, worker, scheduler, provider client, S3 adapter, or API documentation changes are planned.

## Existing Contracts

Backend endpoints already exist and are covered by targeted tests:

- `POST /api/v1/ops/alert-deliveries/preview`
- `POST /api/v1/ops/alert-deliveries/fake-send`

Backend guarantees:

- Admin-only.
- Exact active alert codes only.
- `channel=local_outbox`.
- Preview writes no audit event.
- Fake-send requires `reason` and exact `confirmation=SEND FAKE OPS ALERTS`.
- Fake-send writes compact audit only for non-deduped batches.
- No Slack/email/webhook delivery.
- No provider calls, cleanup, delete, parsing, translation, or Word generation.

## Frontend Contract

Add TS types:

- `OpsAlertDeliveryChannel`
- `OpsAlertDeliveryMode`
- `OpsAlertDeliveryOutcome`
- `OpsAlertDeliveryPreviewRequest`
- `OpsAlertDeliveryFakeSendRequest`
- `OpsAlertDeliverySafetyResponse`
- `OpsAlertDeliveryItemResponse`
- `OpsAlertDeliveryResponse`

Add API wrapper:

```ts
opsAlertDeliveriesApi.preview(payload)
opsAlertDeliveriesApi.fakeSend(payload)
```

## UI Design

Add a panel to `OpsDashboardPage.vue` after the alert list and before the recovery action registry:

- Header:
  - title: `Alert Delivery Fake Outbox`
  - subtitle states local fake outbox only.
  - active alert count and selected count.
- Selection:
  - table of current `opsAlerts.alerts`.
  - multi-select active alert codes.
  - no free-form input.
- Controls:
  - dedupe window number input, 1..1440.
  - preview button.
  - fake-send button opens a confirmation dialog.
- Dialog:
  - selected codes read-only.
  - reason textarea.
  - confirmation input.
  - required phrase displayed from preview result if available, otherwise backend-known phrase.
- Result:
  - delivery id.
  - mode.
  - totals.
  - safety flags.
  - per-alert outcome table.

## Safety

- UI must not imply real external delivery.
- Button labels must say fake/local outbox.
- Fake-send must be disabled when no selected alerts exist.
- Preview and fake-send both use only current active alert codes from backend response.
- Reason and confirmation are enforced by the backend; UI also prevents empty reason / wrong confirmation to reduce accidental requests.
- Refreshing the dashboard clears stale selected alert codes that are no longer active.

## Compatibility

- Additive frontend-only change.
- Existing Ops dashboard data load remains unchanged except selected alert cleanup.
- No route change.
- No backend tests or OpenAPI export required unless backend changes are discovered.

## Risk

- Active alerts can disappear between dashboard load and preview/fake-send. Backend will return conflict; the page surfaces the API error and the Admin can refresh.
- Fake-send writes audit events. The UI must make that explicit before confirmation.
- Large text in alert descriptions may overflow; keep tables fixed layout and use existing Element Plus overflow behavior.
