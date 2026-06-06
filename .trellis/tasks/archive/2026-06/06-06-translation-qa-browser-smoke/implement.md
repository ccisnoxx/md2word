# Translation QA Browser Smoke Implementation Plan

## Status

Smoke completed. No production UI fix was required.

## Completed Work

- Created a temporary Playwright smoke harness under `/private/tmp/md2word-qa-smoke`.
- Used browser-side mock API responses for auth, job detail, and translation QA endpoints.
- Started the existing Vite dev server on `127.0.0.1:3100`.
- Validated available `en2zh_pdf_to_word` QA evidence.
- Validated missing debug archive copy.
- Validated unsupported direct job warning.

## Proposed Steps

1. Start frontend runtime

   - Prefer `npm --prefix frontend run dev`.
   - Use port `3000`.

2. Build mock API responses

   - available QA job
   - missing debug archive QA job
   - unsupported direct job

3. Run browser automation

   - Navigate to QA route for each mocked job.
   - Intercept `/api/v1/document-jobs/...` responses.
   - Capture whether expected text and expanded trace content render.

4. Handle findings

   - If no issue: record smoke result and finish/archive task.
   - If small UI issue: patch only the relevant frontend file, rerun build/smoke, then finish/archive.
   - If larger gap: stop and propose a follow-up task instead of expanding this one.

## Explicit Non-actions

- Do not run PDF parsing.
- Do not call translation providers.
- Do not generate Word.
- Do not add permanent browser test framework unless required by review.
- Do not modify backend API unless smoke reveals a true contract bug.

## Smoke Result

Command:

```bash
PLAYWRIGHT_BROWSERS_PATH=/private/tmp/ms-playwright node /private/tmp/md2word-qa-smoke/translation_qa_browser_smoke.mjs
```

Observed checks:

- available page heading rendered
- summary term trace metric rendered
- segment term trace count rendered
- expanded segment term trace rendered
- `call-level only` AI evidence label rendered
- copy explaining no stable segment-to-call key rendered
- missing debug archive copy rendered
- unavailable source evidence tag rendered
- unsupported direct job warning rendered

Notes:

- The temporary Playwright package and Chromium browser were installed under `/private/tmp`; project dependencies were not changed.
- Chromium required elevated execution because the sandbox blocked macOS Mach port initialization.
- No production code was changed in this smoke task.
