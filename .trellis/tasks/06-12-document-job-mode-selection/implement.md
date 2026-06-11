# Document Job Mode Selection Implementation Plan

## Checklist

- [x] Add centralized frontend document job mode metadata.
- [x] Update `PdfUploadPanel` to render mode selection from metadata and backend readiness.
- [x] Remove `VITE_ENABLE_EN2ZH` usage from the create flow.
- [x] Update changed tests/mocks to include mode readiness.
- [x] Add smoke coverage for selecting `en2zh_pdf_to_word` and unavailable `en2zh` behavior.
- [x] Run frontend unit tests, build, and smoke tests.

## Expected Files

- `frontend/src/utils/format.ts` or a nearby frontend utility for shared mode metadata.
- `frontend/src/components/PdfUploadPanel.vue`.
- `frontend/tests/smoke/core-flow.spec.ts`.
- `frontend/src/env.d.ts` if `VITE_ENABLE_EN2ZH` becomes unused.

## Review Gates

- No backend API schema changes.
- No unsupported future mode values in frontend type unions.
- No user-created jobs can silently submit a disabled translation mode.
