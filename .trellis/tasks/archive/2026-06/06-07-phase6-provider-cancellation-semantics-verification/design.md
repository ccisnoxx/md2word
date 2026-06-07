# Phase 6 provider cancellation semantics verification design

## Boundary

This slice is read-only verification. It does not add a MinerU cancellation client method, does not call MinerU, and does not change fake cancellation execution.

## Backend Contract

Add `GET /api/v1/ops/provider-cancellations/semantics-verification`.

The response includes:

- provider `mineru`
- verification status and decision
- whether public docs support real cancellation
- documented provider operation identifiers currently used by this system
- source summaries and URLs
- blocking reasons and recommended next steps
- safety flags

The integration control plane should replace `provider_cancellation_semantics_unverified` with a verified blocked reason such as `provider_cancellation_unsupported_by_public_docs`.

## Frontend Contract

Ops Dashboard provider cancellation panel should load the report during dashboard refresh and display decision, source count, safety flags, blocking reasons, and source labels/URLs.

## Compatibility

All changes are additive except the control-plane blocking reason text becoming more accurate. Existing fake preview/fake-cancel requests and responses remain unchanged.

## External Documentation Check

Primary public docs checked during this task:

- `https://mineru.net/doc/docs/index_en/`
- `https://mineru.net/doc/docs/quick_usage/api_usage/`

The report records that public docs expose task submission and result query semantics, but no provider-side cancellation endpoint or safe cancellation outcome contract.
