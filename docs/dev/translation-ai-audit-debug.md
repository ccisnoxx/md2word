---
doc_type: dev-guide
slug: translation-ai-audit-debug
component: document-ir-translation
status: current
summary: P1 DocumentIR 翻译 AI 调用审计和全文调试归档规则。
tags: [backend, translation, audit, debug, document-ir]
last_reviewed: 2026-05-30
---

# Translation AI Audit And Debug

P1 `en2zh_pdf_to_word` jobs translate DocumentIR text nodes during the `ir_converting` stage before Word rendering.

## AI Call Audit

Every translation provider call writes an `ai_call_log` document file for the job. The JSON uses `schema_version=ai-call-log/v1` and stores metadata only:

- `job_id`, `trace_id`, provider backend/model, language pair, term version and term snapshot hash
- request/response item counts, character counts and `sha256` hashes
- per-item redacted summaries: item id, character count, line count, hash and non-ASCII flag
- failure type and sanitized error message when the provider call fails

The audit log does not store full source text, translated text, glossary terms, API keys, request headers or model raw payload dumps.

## Full Text Debug Archive

Full prompt and response retention is task-level and off by default.

Required conditions:

- Runtime config `TRANSLATION_DEBUG_ARCHIVE_ENABLED=true`
- Create document job with `debug_full_text=true`
- Job mode is `en2zh_pdf_to_word`

When enabled, the Worker writes an `ai_debug_archive` document file with `schema_version=translation-debug-archive/v1`. It contains the structured provider request and response, including full text and glossary terms, and expires after `TRANSLATION_DEBUG_ARCHIVE_RETENTION_DAYS` days. The default retention is 1 day.

If `debug_full_text=true` is requested while the runtime config is disabled, the API returns `400 invalid_request` and does not create the job.
