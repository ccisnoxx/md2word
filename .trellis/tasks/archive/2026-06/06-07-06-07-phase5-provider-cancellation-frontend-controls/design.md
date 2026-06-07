# Phase 5 provider cancellation frontend controls design

## Scope

Frontend-only slice.

Files to change:

- `frontend/src/api/types.ts`
- `frontend/src/api/opsProviderCancellations.ts`
- `frontend/src/pages/OpsDashboardPage.vue`

No backend code, OpenAPI schema, persistence adapter, config, worker, scheduler, provider client, S3 adapter, document job mutation path, or API documentation changes are planned.

## Existing Backend Contract

Backend endpoints already exist:

- `POST /api/v1/ops/provider-cancellations/preview`
- `POST /api/v1/ops/provider-cancellations/fake-cancel`

Backend guarantees:

- Admin-only.
- Exact `target_type + target_id` target.
- `provider=mineru` only.
- Preview is metadata-only and writes no audit.
- Fake-cancel requires non-empty `reason` and exact `confirmation=FAKE CANCEL PROVIDER OPERATION`.
- Fake-cancel writes compact `ops.provider_cancellation_fake` audit only when eligible and not deduped.
- No real MinerU/provider cancellation.
- No local job status mutation, queue mutation, cleanup, delete, parsing, translation, or Word generation.

## Frontend Contract

Add TS types:

- `OpsProviderCancellationProvider`
- `OpsProviderCancellationTargetType`
- `OpsProviderCancellationMode`
- `OpsProviderCancellationOutcome`
- `OpsProviderCancellationPreviewRequest`
- `OpsProviderCancellationFakeRequest`
- `OpsProviderCancellationTargetResponse`
- `OpsProviderOperationResponse`
- `OpsProviderCancellationSafetyResponse`
- `OpsProviderCancellationResponse`

Add API wrapper:

```ts
opsProviderCancellationsApi.preview(payload)
opsProviderCancellationsApi.fakeCancel(payload)
```

## UI Design

Add a panel to `OpsDashboardPage.vue` after `Alert Delivery Fake Outbox` and before the recovery action registry:

- Header:
  - title: `Provider Cancellation Fake Control`
  - subtitle states fake MinerU cancellation only.
- Input:
  - target type select: `document_job` / `legacy_job`.
  - target id text input.
  - read-only provider field: `mineru`.
  - dedupe window number input, 1..1440.
- Actions:
  - preview button calls metadata-only preview.
  - fake-cancel button opens confirmation dialog after a preview exists.
- Dialog:
  - target and provider operation are read-only.
  - reason textarea.
  - confirmation input.
  - submit disabled unless reason and confirmation match.
- Result:
  - generated time, action mode, outcome, eligible flag.
  - target summary.
  - provider operation summary.
  - missing gates.
  - audit/dedupe fields.
  - safety flags.

## Safety

- UI must not say or imply real provider cancellation.
- Fake-cancel must be disabled until preview target matches current input.
- Preview and fake-cancel must use exact target fields from the form.
- Confirmation phrase is read from preview result if available, otherwise the backend-known fake phrase.
- Safety metadata is surfaced prominently.
- Backend remains the source of truth for eligibility, dedupe, confirmation, audit write, and Admin auth.

## Compatibility

- Additive frontend-only change.
- Existing dashboard data load is unchanged.
- No route changes.
- No backend tests or OpenAPI export required because backend contract is unchanged.

## Risks

- Operators may confuse fake provider cancellation with local job cancellation or real MinerU cancellation; panel and dialog copy must explicitly separate them.
- Target state can change between preview and fake-cancel; backend returns conflict and UI surfaces the API error.
- Compact audit is still the only durable evidence until the structured audit details Phase 5 slice lands.
