# Translation result QA design

## Current State

`JobDetailPage` 已经展示任务状态、文件/结果区、事件流和任务上下文提案入口。后端 `document-jobs` 已有任务详情、事件、文件汇总和文件下载授权 API；`document_ir`、`ai_call_log`、`ai_debug_archive` 也会作为 `DocumentFileRecord` 绑定到任务。

当前缺口是：没有一个页面把“翻译结果证据”组织给 QA/Ops 查看，也没有任务级复核状态。现有 `ai_call_log` 是 metadata-only，不包含完整 prompt/response/正文；`ai_debug_archive` 才包含全文，但受任务开关和保留期限制，默认不一定存在。因此本任务不能承诺所有任务都有完整源文/译文段落对照。

## Scope

本子任务只做一个小的任务级翻译 QA 切片：

- Backend:
  - 在 `DocumentJobRecord` 增加轻量 QA 字段。
  - 增加 `GET /api/v1/document-jobs/{job_id}/translation-qa` 证据汇总接口。
  - 增加 `PATCH /api/v1/document-jobs/{job_id}/translation-qa` 复核状态接口。
  - 从现有文件产物读取 `document_ir`、`ai_call_log`、可选 `ai_debug_archive`，不触发任何主流程。
  - 给 `DocumentJobService` 注入现有 `FileUploadService`，只用于读取已登记文件内容。
- Frontend:
  - 新增 `TranslationResultQaPage.vue`。
  - 新增 `/jobs/:jobId/translation-qa` 路由。
  - 在 `JobDetailPage` 对 `en2zh_pdf_to_word` 任务增加入口按钮。
  - 新增 API wrapper 和 TypeScript contracts。
- Tests:
  - 增加/更新 `tests/test_fastapi_jobs_backend.py` 的最小 API 覆盖。
  - 前端跑最小类型检查或构建。

不做：

- 不重新运行 pdf-mineru 解析、翻译、Word 生成。
- 不做跨任务翻译结果列表页。
- 不做完整段落质检工作台或在线编辑译文。
- 不做完整术语规则 CRUD 工作台。
- 不做真实文件删除、保留策略或存储管理。
- 不把 metadata-only `ai_call_log` 伪装成完整 LLM 复现包。

## Backend Contract

Files to change:

- `app/domains/document_jobs/models.py`
- `app/domains/document_jobs/schemas.py`
- `app/domains/document_jobs/service.py`
- `app/domains/document_jobs/router.py`
- `app/main.py`
- `tests/test_fastapi_jobs_backend.py`
- `docs/api/openapi.json` if OpenAPI snapshot changes

### Model fields

Add additive fields to `DocumentJobRecord` and `DocumentJobResponse`:

- `translation_qa_status`: `unreviewed | approved | needs_fix | blocked`, default `unreviewed`
- `translation_qa_issue_type`: `translation | terminology | layout | source_quality | artifact_missing | other | null`
- `translation_qa_note`: `str | null`
- `translation_qa_reviewed_by`: `str | null`
- `translation_qa_reviewed_at`: `datetime | null`

Because file/sqlite/mysql document job adapters store the full job payload JSON, this does not require a database schema migration.

### `GET /api/v1/document-jobs/{job_id}/translation-qa`

Response shape:

```json
{
  "job_id": "docjob_xxx",
  "available": true,
  "availability_reason": null,
  "qa": {
    "status": "unreviewed",
    "issue_type": null,
    "note": null,
    "reviewed_by": null,
    "reviewed_at": null
  },
  "artifacts": {
    "document_ir_file_id": "file_docir",
    "ai_call_log_file_ids": ["file_log"],
    "ai_debug_archive_file_ids": []
  },
  "summary": {
    "final_segment_count": 42,
    "quality_flags": ["layout_wide_table:block_0003"],
    "ai_call_count": 1,
    "ai_call_statuses": {"succeeded": 1},
    "term_trace_count": 3,
    "source_comparison_available": false,
    "source_comparison_reason": "ai_debug_archive_missing"
  },
  "segments": [
    {
      "id": "block_0001.text",
      "block_id": "block_0001",
      "page_index": 0,
      "order": 1,
      "block_type": "paragraph",
      "field": "text",
      "index": null,
      "source_text": null,
      "ai_translation_text": null,
      "final_text": "最终译文",
      "source_available": false
    }
  ],
  "term_traces": [
    {
      "segment_id": "block_0001.text",
      "batch_id": "document_ir_provider_request_0001",
      "translation_term_set_id": "translation-terms-en2zh",
      "translation_term_version": "2026.06.01-1",
      "source_term": "FPGA",
      "target_term": "现场可编程门阵列",
      "match_start": 12,
      "match_end": 16,
      "context": {"char_count": 80, "sha256": "sha256:..."},
      "injected_to_glossary": true,
      "provider_trace_id": null
    }
  ]
}
```

Rules:

- First call `get_job(job_id, user=user)` so visibility remains the source of truth.
- Return `available=false` with a clear reason for non-`en2zh_pdf_to_word` jobs or missing required artifacts.
- Read only existing `DocumentFileRecord` artifacts for the same visible job.
- `document_ir` supplies final translated text segments and quality flags.
- `ai_call_log` supplies provider metadata and term trace summaries.
- `ai_debug_archive` may supply source/AI translated text only if file exists, is uploaded, and is not expired.
- Do not return raw prompt, headers, secrets, or whole debug archive payload.

### `PATCH /api/v1/document-jobs/{job_id}/translation-qa`

Request:

```json
{
  "status": "needs_fix",
  "issue_type": "terminology",
  "note": "FPGA 译法不一致，需要提交翻译术语建议。"
}
```

Rules:

- Validate job visibility with `get_job(job_id, user=user)`.
- Only accept `en2zh_pdf_to_word` jobs.
- Persist QA fields on the job record.
- Append `translation_qa_updated` event with status, issue type, actor, and note length only. Do not put full segment text in event payload.
- Return the updated QA summary or full `DocumentJobResponse` companion response.

## Frontend Contract

Files to change:

- `frontend/src/api/types.ts`
- `frontend/src/api/documentJobs.ts`
- `frontend/src/router/index.ts`
- `frontend/src/pages/JobDetailPage.vue`
- `frontend/src/pages/TranslationResultQaPage.vue`

Page behavior:

- `JobDetailPage` shows a “翻译 QA” action only when `job.mode === "en2zh_pdf_to_word"`.
- `TranslationResultQaPage` loads:
  - `documentJobsApi.get(jobId)`
  - `documentJobsApi.getTranslationQa(jobId)`
- Page sections:
  - task summary and bound resource versions
  - evidence availability and artifact IDs
  - QA status form
  - final text segment table
  - term trace table
  - AI call summary
- Segment table must explicitly distinguish:
  - final text available from `document_ir`
  - source/AI response unavailable because `ai_debug_archive` is absent or expired
- The page may link to existing task detail and proposal creation flow, but it does not implement proposal CRUD itself.

## Compatibility

- Existing document job creation, retry, cancel, archive, file download, and proposal APIs remain unchanged.
- Existing persisted jobs validate through default QA fields.
- OpenAPI changes are additive.
- `direct_pdf_to_word` jobs remain valid and simply return translation QA unavailable.

## Risks

- Full paragraph comparison is only possible when full-text debug archive exists. The UI must not hide this limitation.
- Reading generated artifacts inside a request is acceptable for the MVP, but response size should stay bounded. The first implementation should cap returned segments, for example `limit=200`, and expose counts.
- QA status on the job record is task-level, not per segment. Segment-level annotations remain deferred to a future full QA workbench.
