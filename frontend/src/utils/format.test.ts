import { describe, expect, it } from "vitest";

import type { DocumentJobResponse } from "@/api/types";
import {
  documentJobActionDisabledReason,
  documentJobModeCreateLanguage,
  documentJobModeOptions,
  documentJobModeRequiresTranslationResources,
  documentJobModeSupportsTranslationQa,
  isDocumentJobActionEnabled,
} from "@/utils/format";

function buildJob(
  availableActions: DocumentJobResponse["available_actions"],
): DocumentJobResponse {
  return {
    id: "docjob_unit",
    tenant_id: "tenant_default",
    company_id: "company_default",
    created_by: "user_operator",
    source_file_id: "file_unit",
    source_job_id: null,
    mode: "direct_pdf_to_word",
    document_language: "auto",
    status: "succeeded",
    stage: "completed",
    progress: 100,
    template_version_id: "template_default",
    term_version_id: null,
    result_file_id: "file_result",
    mineru_raw_result_file_id: null,
    document_ir_file_id: null,
    image_asset_file_ids: [],
    debug_full_text_enabled: false,
    mineru_batch_id: null,
    mineru_data_id: null,
    failed_stage: null,
    error_code: null,
    error_message: null,
    retry_count: 0,
    timeout_at: null,
    started_at: null,
    completed_at: "2026-06-11T00:00:00Z",
    canceled_at: null,
    archived_at: null,
    archived_by: null,
    deleted_at: null,
    deleted_by: null,
    delete_reason: null,
    translation_qa_status: "unreviewed",
    translation_qa_issue_type: null,
    translation_qa_note: null,
    translation_qa_reviewed_by: null,
    translation_qa_reviewed_at: null,
    request_snapshot: {},
    available_actions: availableActions,
    created_at: "2026-06-11T00:00:00Z",
    updated_at: "2026-06-11T00:00:00Z",
  };
}

describe("document job action contract", () => {
  it("uses server-provided action availability instead of local status fallback", () => {
    const job = buildJob({
      download: { enabled: false, disabled_reason: "结果文件已过期。", retryable: false },
      retry: { enabled: false, disabled_reason: "只有 failed 文档任务允许重试。", retryable: false },
      cancel: { enabled: false, disabled_reason: "只有 pending、queued、running 任务允许取消。", retryable: false },
      archive: { enabled: true, disabled_reason: null, retryable: false },
      unarchive: { enabled: false, disabled_reason: "任务未归档。", retryable: false },
      clone: { enabled: true, disabled_reason: null, retryable: false },
      delete: { enabled: true, disabled_reason: null, retryable: false },
    });

    expect(isDocumentJobActionEnabled(job, "download")).toBe(false);
    expect(documentJobActionDisabledReason(job, "download")).toBe("结果文件已过期。");
    expect(isDocumentJobActionEnabled(job, "archive")).toBe(true);
    expect(documentJobActionDisabledReason(job, "archive")).toBe("");
    expect(isDocumentJobActionEnabled(job, "delete")).toBe(true);
  });
});

describe("document job mode metadata", () => {
  it("defines create language and translation-resource behavior in one place", () => {
    expect(documentJobModeOptions.map((option) => option.mode)).toEqual([
      "direct_pdf_to_word",
      "en2zh_pdf_to_word",
    ]);

    expect(documentJobModeCreateLanguage("direct_pdf_to_word")).toBe("auto");
    expect(documentJobModeRequiresTranslationResources("direct_pdf_to_word")).toBe(false);
    expect(documentJobModeSupportsTranslationQa("direct_pdf_to_word")).toBe(false);

    expect(documentJobModeCreateLanguage("en2zh_pdf_to_word")).toBe("en");
    expect(documentJobModeRequiresTranslationResources("en2zh_pdf_to_word")).toBe(true);
    expect(documentJobModeSupportsTranslationQa("en2zh_pdf_to_word")).toBe(true);
  });
});
