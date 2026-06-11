# Document Job Mode Selection Design

## Decision

Use backend config summary readiness as the source of truth for whether `en2zh_pdf_to_word` can be selected. Remove the frontend-only `VITE_ENABLE_EN2ZH` visibility gate from the create flow.

## Current State

- `PdfUploadPanel` already submits `mode` and maps `en2zh_pdf_to_word` to `document_language=en`.
- The task mode selector is hidden unless `VITE_ENABLE_EN2ZH === "true"`.
- Mode labels and mode-specific checks are duplicated across upload, detail, table, template validation, and QA pages.
- `GET /api/v1/document-jobs/config-summary` already returns `readiness.en2zh_available`.

## Target State

- `PdfUploadPanel` always renders a mode selector.
- The selector options come from a frontend mode helper that defines label, create language, translation-resource requirement, and QA support per mode.
- `en2zh_pdf_to_word` is disabled when `configSummary.readiness.en2zh_available` is false.
- Mode-specific translation resource controls and payload fields use helper predicates instead of raw string comparisons where the create flow is touched.
- Existing backend contracts stay unchanged.

## Data Flow

1. Create page mounts `PdfUploadPanel`.
2. `PdfUploadPanel` loads document job config summary.
3. The component builds mode options from local mode metadata plus config readiness.
4. User chooses a selectable mode.
5. Submit uses the selected mode metadata to set `mode` and `document_language`.
6. Optional admin resource overrides are included only when the selected mode requires translation resources.

## Non-Goals

- Do not add `zh2ru` to `DocumentJobMode`.
- Do not add backend translation profiles, term sets, QA behavior, or conversion logic.
- Do not change the document job API wire shape.
- Do not refactor unrelated job detail, list, or template validation behavior beyond using a shared label source if needed.

## Risks

- Config summary smoke mocks must include `en2zh_available`; otherwise UI tests may represent a legacy payload shape that no longer proves the selector behavior.
- If `en2zh_available` is false after a user already selected `en2zh`, the component must return to direct mode or disable submission predictably.

## Verification

- Frontend smoke test proves selector visibility without `VITE_ENABLE_EN2ZH`.
- Frontend smoke test proves `en2zh` request payload has `mode=en2zh_pdf_to_word` and `document_language=en`.
- Frontend smoke test proves unavailable `en2zh` is disabled while direct creation remains available.
- `npm run test:unit`, `npm run build`, and `npm run test:smoke` pass.
