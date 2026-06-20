import { describe, expect, it } from "vitest";

import type { DocumentFileResponse, DocumentJobResponse } from "@/api/types";
import {
  buildDocumentJobDiagnosticRecommendation,
  buildDocumentJobQualityEvidence,
  documentJobActionDisabledReason,
  documentJobQualityFlagText,
  documentJobModeCreateLanguage,
  documentJobModeOptions,
  documentJobModeRequiresTranslationResources,
  documentJobModeSupportsTranslationQa,
  isDocumentJobActionEnabled,
  shouldShowDocumentJobAction,
} from "@/utils/format";

function buildJob(
  availableActions: DocumentJobResponse["available_actions"],
  overrides: Partial<DocumentJobResponse> = {},
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
    ...overrides,
  };
}

function buildFile(overrides: Partial<DocumentFileResponse>): DocumentFileResponse {
  return {
    id: "file_unit",
    tenant_id: "tenant_default",
    company_id: "company_default",
    job_id: "docjob_unit",
    file_type: "generated_word",
    storage_provider: "local",
    bucket: "default",
    object_key: "objects/file_unit",
    original_filename: "result.docx",
    mime_type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    size_bytes: 1024,
    checksum_sha256: null,
    etag: null,
    status: "uploaded",
    expires_at: null,
    metadata: {},
    created_by: "user_operator",
    created_at: "2026-06-11T00:00:00Z",
    updated_at: "2026-06-11T00:00:00Z",
    ...overrides,
  };
}

const defaultAvailableActions: DocumentJobResponse["available_actions"] = {
  download: { enabled: true, disabled_reason: null, retryable: false },
  retry: { enabled: false, disabled_reason: "只有 failed 文档任务允许重试。", retryable: false },
  cancel: { enabled: false, disabled_reason: "只有 pending、queued、running 任务允许取消。", retryable: false },
  archive: { enabled: true, disabled_reason: null, retryable: false },
  unarchive: { enabled: false, disabled_reason: "任务未归档。", retryable: false },
  clone: { enabled: true, disabled_reason: null, retryable: false },
  delete: { enabled: true, disabled_reason: null, retryable: false },
};

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

  it("hides task delete when the server reports it is admin-only", () => {
    const operatorJob = buildJob({
      download: { enabled: true, disabled_reason: null, retryable: false },
      retry: { enabled: false, disabled_reason: "只有 failed 文档任务允许重试。", retryable: false },
      cancel: { enabled: false, disabled_reason: "只有 pending、queued、running 任务允许取消。", retryable: false },
      archive: { enabled: true, disabled_reason: null, retryable: false },
      unarchive: { enabled: false, disabled_reason: "任务未归档。", retryable: false },
      clone: { enabled: true, disabled_reason: null, retryable: false },
      delete: { enabled: false, disabled_reason: "只有 admin 可以删除文档任务。", retryable: false },
    });
    const adminRunningJob = buildJob({
      ...operatorJob.available_actions,
      delete: { enabled: false, disabled_reason: "只有终态任务允许删除；处理中任务请先取消。", retryable: false },
    });
    const adminTerminalJob = buildJob({
      ...operatorJob.available_actions,
      delete: { enabled: true, disabled_reason: null, retryable: false },
    });

    expect(shouldShowDocumentJobAction(operatorJob, "delete")).toBe(false);
    expect(shouldShowDocumentJobAction(adminRunningJob, "delete")).toBe(true);
    expect(shouldShowDocumentJobAction(adminTerminalJob, "delete")).toBe(true);
    expect(shouldShowDocumentJobAction(operatorJob, "download")).toBe(true);
  });
});

describe("document job diagnostic recommendation", () => {
  it("uses backend retry availability for failed-job guidance", () => {
    const retryableJob = buildJob({
      ...defaultAvailableActions,
      retry: { enabled: true, disabled_reason: null, retryable: true },
    }, {
      status: "failed",
      stage: "failed",
      failed_stage: "parsing",
      error_code: "mineru_failed",
    });
    const blockedJob = buildJob({
      ...defaultAvailableActions,
      retry: { enabled: false, disabled_reason: "人工锁定。", retryable: false },
    }, {
      status: "failed",
      stage: "failed",
      failed_stage: "rendering",
      error_code: "render_failed",
    });

    expect(buildDocumentJobDiagnosticRecommendation({ job: retryableJob }).actionLabel).toBe("使用现有重试动作");
    expect(buildDocumentJobDiagnosticRecommendation({ job: blockedJob }).description).toContain("人工锁定");
  });

  it("surfaces completed jobs with missing result evidence", () => {
    const job = buildJob(defaultAvailableActions, { status: "succeeded", result_file_id: null });

    expect(buildDocumentJobDiagnosticRecommendation({ job, missingResult: true })).toMatchObject({
      type: "warning",
      actionLabel: "刷新文件证据",
    });
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

describe("document job quality evidence", () => {
  it("summarizes and deduplicates quality flags from generated Word and DocumentIR metadata", () => {
    const job = buildJob(defaultAvailableActions, {
      result_file_id: "file_word",
      document_ir_file_id: "file_ir",
    });
    const summary = buildDocumentJobQualityEvidence(job, [
      buildFile({
        id: "file_word",
        file_type: "generated_word",
        metadata: {
          schema_version: "document-ir/v2",
          renderer_mode: "layout_v2",
          layout_page_count: 2,
          layout_block_count: 6,
          layout_quality_flags: ["layout_wide_table:block_0003"],
          quality_flags: ["docx_latex_residue:2"],
          docx_quality: {
            editable_content_available: true,
            image_only_suspected: false,
            heading_paragraphs: 3,
            heading_like_unstyled_paragraphs: 1,
            numbering_paragraphs: 2,
            manual_list_marker_paragraphs: 1,
            toc_tab_leader_paragraphs: 1,
            plain_toc_entry_paragraphs: 1,
            table_count: 2,
            wide_table_count: 1,
            table_header_rows: 2,
            table_no_split_rows: 12,
            latex_residue_count: 2,
          },
        },
      }),
      buildFile({
        id: "file_ir",
        file_type: "document_ir",
        original_filename: "document_ir_v2.json",
        mime_type: "application/json",
        metadata: {
          quality_flags: ["layout_wide_table:block_0003", "layout_caption_binding:block_0003"],
        },
      }),
      buildFile({
        id: "file_log",
        file_type: "ai_call_log",
        original_filename: "ai-call-log.json",
        mime_type: "application/json",
        metadata: { quality_flags: ["unsupported_block_type:ignored_log"] },
      }),
    ]);

    expect(summary.status).toBe("manual_review_required_with_flags");
    expect(summary.flags).toEqual([
      "docx_latex_residue:2",
      "layout_wide_table:block_0003",
      "layout_caption_binding:block_0003",
    ]);
    expect(summary.evidenceItems).toContainEqual({ label: "Renderer", value: "layout_v2", mono: true });
    expect(summary.evidenceItems).toContainEqual({ label: "可编辑内容", value: "是", mono: true });
    expect(summary.evidenceItems).toContainEqual({ label: "疑似整页截图", value: "否", mono: true });
    expect(summary.evidenceItems).toContainEqual({ label: "疑似标题", value: "1", mono: true });
    expect(summary.evidenceItems).toContainEqual({ label: "手写列表", value: "1", mono: true });
    expect(summary.evidenceItems).toContainEqual({ label: "纯文本目录", value: "1", mono: true });
    expect(summary.evidenceItems).toContainEqual({ label: "宽表", value: "1", mono: true });
    expect(summary.evidenceItems).toContainEqual({ label: "表头重复", value: "2", mono: true });
    expect(summary.evidenceItems).toContainEqual({ label: "LaTeX 残留", value: "2", mono: true });
    expect(documentJobQualityFlagText("layout_wide_table:block_0003")).toBe("宽表 · layout_wide_table:block_0003");
    expect(documentJobQualityFlagText("docx_latex_residue:2")).toBe("LaTeX 残留 · docx_latex_residue:2");
    expect(documentJobQualityFlagText("docx_manual_list_markers:1")).toBe("手写列表符号 · docx_manual_list_markers:1");
    expect(documentJobQualityFlagText("docx_plain_toc_entries:1")).toBe("纯文本目录项 · docx_plain_toc_entries:1");
    expect(documentJobQualityFlagText("docx_unstyled_heading_candidates:1")).toBe("疑似标题未样式化 · docx_unstyled_heading_candidates:1");
    expect(documentJobQualityFlagText("docx_wide_table_without_landscape:1")).toBe("宽表未横版 · docx_wide_table_without_landscape:1");
  });

  it("keeps successful output in manual review until an admin signs off outside automatic evidence", () => {
    const job = buildJob(defaultAvailableActions, { result_file_id: "file_word" });
    const summary = buildDocumentJobQualityEvidence(job, [
      buildFile({
        id: "file_word",
        file_type: "generated_word",
        metadata: { renderer_mode: "layout_v2" },
      }),
    ]);

    expect(summary.status).toBe("manual_review_required");
    expect(summary.flags).toEqual([]);
    expect(summary.title).toContain("人工复核");
  });
});
