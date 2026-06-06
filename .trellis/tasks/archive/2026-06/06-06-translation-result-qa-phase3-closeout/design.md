# Translation Result QA Phase 3 Closeout Design

## Scope

This is a planning-only acceptance task. It does not change backend, frontend, API contracts, tests, dependencies, or runtime behavior.

## Acceptance Matrix

| Phase 3 area | Verdict | Evidence |
| --- | --- | --- |
| 翻译结果/质检页 | Complete | `TranslationResultQaPage.vue` exists, route `/jobs/:jobId/translation-qa` is wired, and job detail exposes the entry only for `en2zh_pdf_to_word`. |
| 段落对照 | Complete with artifact-dependent depth | Backend QA response returns final text segments from `document_ir`; source/AI translation text is shown when `ai_debug_archive` is available and explains unavailable reasons when missing, expired, or empty. |
| 术语命中 trace | Complete | `term_traces` are read from `ai_call_log`; the frontend groups term hits by `segment_id` in the segment-first trace view and keeps unmatched traces visible. |
| AI call log 可视化 | Complete with honest granularity | `ai_calls` are shown as metadata-only evidence. The UI explicitly labels them `call-level only` because current artifacts do not expose a stable segment-to-call key. |
| debug archive 诊断入口 | Complete | QA evidence displays `ai_debug_archive` artifact IDs and source-comparison status; task detail file/result handling already recognizes `ai_debug_archive` as a downloadable diagnostic artifact when available. |
| 任务级 QA 状态、复核状态、问题归因 | Complete | Backend model/API persist `translation_qa_status`, `translation_qa_issue_type`, reviewer, reviewed time, and notes; job detail/list expose QA status and list filtering. |

## Key Evidence Sources

- Roadmap: `.trellis/tasks/archive/2026-06/06-03-product-roadmap/{prd.md,design.md,implement.md}`
- Base Phase 3 slice: `.trellis/tasks/archive/2026-06/06-04-translation-result-qa/{prd.md,design.md,implement.md}`
- Gap audit: `.trellis/tasks/archive/2026-06/06-06-translation-result-qa-gap-audit/{prd.md,design.md,implement.md}`
- Visibility hardening: `.trellis/tasks/archive/2026-06/06-06-translation-qa-visibility-hardening/{prd.md,design.md,implement.md}`
- Segment trace hardening: `.trellis/tasks/archive/2026-06/06-06-translation-qa-segment-trace-hardening/{prd.md,design.md,implement.md}`
- Browser smoke: `.trellis/tasks/archive/2026-06/06-06-translation-qa-browser-smoke/{prd.md,design.md,implement.md}`
- Current code evidence:
  - `app/domains/document_jobs/{models.py,schemas.py,router.py,service.py}`
  - `frontend/src/pages/{TranslationResultQaPage.vue,JobDetailPage.vue,JobsPage.vue}`
  - `frontend/src/components/JobTable.vue`
  - `frontend/src/api/{documentJobs.ts,types.ts}`
  - `frontend/src/router/index.ts`
  - `tests/test_fastapi_jobs_backend.py`
  - `docs/api/document-jobs.md`

## Non-blocking Constraints

- AI calls remain task/call-level metadata. Current artifacts do not support a defensible per-segment AI call join key, so the UI must not imply one.
- Source/AI translated text comparison depends on `ai_debug_archive` availability and retention. Missing archive states are expected and already surfaced.
- Browser smoke was recorded as a temporary Playwright harness under `/private/tmp`; the project did not add a permanent browser test framework in Phase 3.
- Full online translation editing, per-segment QA persistence, automated scoring, and cross-task QA workbench are future enhancements, not blockers for this Phase 3 closeout.

## Closeout Decision

Phase 3 can be closed as the roadmap's current Result QA and Traceability slice. Remaining work should be treated as follow-up roadmap candidates, not unfinished Phase 3 acceptance.
