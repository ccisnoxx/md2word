# Phase 6 real alert delivery adapter contract design

## Boundary

This slice only fixes the adapter contract and fake parity proof. It must not create a real provider adapter, resolve secret values, send notifications, or mark `alert_delivery` ready.

## Backend contract

Add `GET /api/v1/ops/alert-deliveries/adapter-contract`.

The response describes:

- `contract_version`
- supported real channels: `slack`, `email`, `webhook`
- fake adapter id and mode
- required request/result/audit/safety fields
- parity checks that the fake path satisfies
- safe config summary from `OPS_ALERT_DESTINATIONS_JSON`
- read-only safety flags

Extend existing alert delivery preview/fake-send items with `adapter_result` using the same contract version. Fake-send audit details should persist this evidence.

Integration control plane remains blocked for real alert delivery, but safe config may state that adapter contract and fake parity are present.

## Frontend contract

Extend Ops Dashboard Alert Delivery section with a read-only adapter contract panel and show adapter version/mode per fake delivery item.

## Compatibility

All changes are additive:

- existing preview/fake-send request contracts stay unchanged
- existing fake delivery behavior remains local audit/outbox only
- existing real-integration flags stay disabled-by-default

## Risks

Future real adapters may need provider-specific response fields. The contract should include generic nullable fields such as `provider_request_id`, `error_code`, `retryable`, and `timeout_seconds` without forcing a provider-specific payload into audit or API responses.
