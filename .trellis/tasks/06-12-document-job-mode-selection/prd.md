# Document job mode selection

## Goal

Expose document job conversion mode selection on the PDF upload/create flow so operators can choose direct PDF to Word or English PDF to Chinese Word before creating a job.

## Requirements

- The create job page must always show a task mode selector.
- `direct_pdf_to_word` remains the default mode and creates a direct PDF to Word job.
- `en2zh_pdf_to_word` is visible but only selectable when backend config summary reports `readiness.en2zh_available=true`.
- Selecting `en2zh_pdf_to_word` must create a document job with `mode=en2zh_pdf_to_word` and `document_language=en`.
- Selecting `direct_pdf_to_word` must create a document job with `mode=direct_pdf_to_word` and `document_language=auto`.
- Admin-only translation term set and translation profile controls remain visible/submitted only for `en2zh_pdf_to_word`.
- Future modes such as `zh2ru` are not exposed or added to the API contract in this task.
- Frontend mode labels and mode-specific behavior should be centralized enough that adding a future backend-supported mode does not require scattered hardcoded edits.

## Acceptance Criteria

- [x] Operators can see the task mode selector on the create job page without setting `VITE_ENABLE_EN2ZH`.
- [x] When `en2zh_available=true`, operators can select English to Chinese mode and the create request sends the correct mode/language.
- [x] When `en2zh_available=false`, English to Chinese mode is disabled with an explicit UI reason, while direct mode remains usable.
- [x] Existing direct conversion behavior remains unchanged.
- [x] The UI does not show or submit `zh2ru` or any other unsupported future mode.
- [x] Unit, build, and smoke checks covering the changed frontend behavior pass.

## Notes

- Backend `POST /api/v1/document-jobs` already supports `direct_pdf_to_word` and `en2zh_pdf_to_word`; this task does not change the backend API schema.
