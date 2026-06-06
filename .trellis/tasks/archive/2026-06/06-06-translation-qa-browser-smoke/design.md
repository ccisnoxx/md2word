# Translation QA Browser Smoke Design

## Scope

This smoke task validates the current Translation QA detail page in a real frontend runtime. It should not execute document job processing.

## Data Source Decision

Recommended source: browser-side mock API.

Reasoning:

- It avoids creating real document jobs.
- It avoids `pdf-mineru`, translation provider calls, and Word generation.
- It can deterministically cover states that are hard to produce from a single fixture, including available QA evidence, missing debug archive, and unsupported direct jobs.
- The frontend API client already calls stable `/api/v1/document-jobs/...` URLs, so a browser automation layer can intercept responses without changing production code.

Fallback source: backend test runtime only if browser-side interception is unavailable. If used, it must still avoid worker execution and main flow.

## Smoke Scenarios

1. Available `en2zh_pdf_to_word` QA page

   Mock:

   - `GET /api/v1/document-jobs/docjob_qa_smoke`
   - `GET /api/v1/document-jobs/docjob_qa_smoke/translation-qa`

   Verify:

   - heading `翻译 QA`
   - task mode label
   - QA status form
   - segment table row
   - evidence tags such as source comparison and term hit count
   - expanded segment trace table
   - call-level AI evidence copy

2. Missing debug archive

   Mock QA response with `source_comparison_available=false` and `source_comparison_reason=ai_debug_archive_missing`.

   Verify:

   - page remains usable
   - source/AI translation columns show unavailable reason
   - term trace and final text still render

3. Unsupported direct job

   Mock direct job and QA response with `available=false`, `availability_reason=unsupported_mode`.

   Verify:

   - warning says Translation QA is not applicable
   - no misleading translation evidence is shown as available

## Execution Strategy

- Use a local Vite dev server or preview server.
- Use browser automation to navigate directly to `/jobs/:jobId/translation-qa`.
- Intercept API responses in the browser automation layer.
- Prefer a temporary smoke script under `/private/tmp` or another non-repo temp path unless a permanent test artifact is explicitly needed.

## Risk Boundaries

- Do not add or change app routes for smoke only.
- Do not change backend behavior to make smoke easier.
- Do not add production mock switches.
- If browser smoke finds a UI defect, apply the smallest frontend fix and rerun only relevant validation.

## Verification

- Browser smoke observations.
- `npm --prefix frontend run build` if any frontend file changes.
- `git diff --check`.
