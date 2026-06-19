import { describe, expect, it } from "vitest";

import type { DocumentJobResponse, TranslationQaStatus } from "@/api/types";
import { selectNextTranslationQaJob } from "@/utils/translationQa";

function buildJob(id: string, translationQaStatus: TranslationQaStatus): DocumentJobResponse {
  return {
    id,
    tenant_id: "tenant_default",
    company_id: "company_default",
    created_by: "user_operator",
    source_file_id: `${id}_source`,
    source_job_id: null,
    mode: "en2zh_pdf_to_word",
    document_language: "en",
    status: "succeeded",
    stage: "completed",
    progress: 100,
    template_version_id: "template_default",
    term_version_id: null,
    result_file_id: `${id}_result`,
    mineru_raw_result_file_id: null,
    document_ir_file_id: `${id}_ir`,
    image_asset_file_ids: [],
    debug_full_text_enabled: true,
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
    translation_qa_status: translationQaStatus,
    translation_qa_issue_type: null,
    translation_qa_note: null,
    translation_qa_reviewed_by: null,
    translation_qa_reviewed_at: null,
    request_snapshot: {
      source_file: { original_filename: `${id}.pdf` },
    },
    available_actions: {
      download: { enabled: true, disabled_reason: null, retryable: false },
      retry: { enabled: false, disabled_reason: null, retryable: false },
      cancel: { enabled: false, disabled_reason: null, retryable: false },
      archive: { enabled: true, disabled_reason: null, retryable: false },
      unarchive: { enabled: false, disabled_reason: null, retryable: false },
      clone: { enabled: true, disabled_reason: null, retryable: false },
      delete: { enabled: true, disabled_reason: null, retryable: false },
    },
    created_at: "2026-06-11T00:00:00Z",
    updated_at: "2026-06-11T00:00:00Z",
  };
}

describe("selectNextTranslationQaJob", () => {
  it("uses blocked, needs_fix, unreviewed, approved priority over current list order", () => {
    const jobs = [
      buildJob("current", "blocked"),
      buildJob("approved_first", "approved"),
      buildJob("unreviewed_first", "unreviewed"),
      buildJob("needs_fix_first", "needs_fix"),
      buildJob("blocked_first", "blocked"),
    ];

    expect(selectNextTranslationQaJob(jobs, "current")?.id).toBe("blocked_first");
  });

  it("keeps the current queue order within the same status priority", () => {
    const jobs = [
      buildJob("current", "approved"),
      buildJob("needs_fix_first", "needs_fix"),
      buildJob("needs_fix_second", "needs_fix"),
      buildJob("unreviewed_first", "unreviewed"),
    ];

    expect(selectNextTranslationQaJob(jobs, "current")?.id).toBe("needs_fix_first");
  });

  it("excludes the current job and returns null when no next job exists", () => {
    expect(selectNextTranslationQaJob([buildJob("current", "blocked")], "current")).toBeNull();
  });
});
