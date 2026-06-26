import { describe, expect, it } from "vitest";

import type { DocumentJobTranslationBatchSummaryResponse } from "@/api/types";
import {
  summarizeTranslationBatches,
  translationBatchAiCallLogSummaryText,
  translationBatchAttemptText,
  translationBatchErrorSummaryText,
  translationBatchFlagTexts,
  translationBatchPageRangeText,
  translationBatchRowClassName,
  translationBatchStatusTagType,
  translationBatchStatusText,
} from "@/utils/translationBatches";

function buildBatch(
  overrides: Partial<DocumentJobTranslationBatchSummaryResponse> = {},
): DocumentJobTranslationBatchSummaryResponse {
  return {
    batch_id: "batch_001",
    job_id: "docjob_batch",
    generation: 0,
    root_batch_id: "batch_001",
    parent_batch_id: null,
    status: "succeeded",
    page_start: 1,
    page_end: 3,
    item_count: 12,
    char_count: 1200,
    split_level: 0,
    attempt_count: 1,
    max_attempts: 2,
    deterministic_batch_count: 2,
    provider_call_budget: 24,
    source_document_ir_file_id: "file_source_ir",
    result_file_id: "file_result",
    ai_call_log_file_ids: ["file_ai_1"],
    debug_archive_file_ids: [],
    finish_reason: "stop",
    usage: {},
    response_id: "resp_1",
    error_code: null,
    error_message: null,
    retryable: false,
    truncation_retry: false,
    lease_expires_at: null,
    created_at: "2026-06-26T00:00:00Z",
    updated_at: "2026-06-26T00:01:00Z",
    ...overrides,
  };
}

describe("translation batch display helpers", () => {
  it("labels known statuses and falls back to raw unknown status", () => {
    expect(translationBatchStatusText("running")).toBe("运行中");
    expect(translationBatchStatusText("provider_paused")).toBe("provider_paused");
  });

  it("maps failed, split, truncated, active, and succeeded batches to visual states", () => {
    expect(translationBatchStatusTagType(buildBatch({ status: "failed" }))).toBe("danger");
    expect(translationBatchStatusTagType(buildBatch({ status: "split" }))).toBe("warning");
    expect(translationBatchStatusTagType(buildBatch({ status: "running" }))).toBe("info");
    expect(translationBatchStatusTagType(buildBatch({ status: "succeeded" }))).toBe("success");
    expect(translationBatchStatusTagType(buildBatch({ status: "succeeded", finish_reason: "length" }))).toBe("warning");
  });

  it("formats page range, attempt count, log summary, and error summary", () => {
    expect(translationBatchPageRangeText(buildBatch({ page_start: 2, page_end: 2 }))).toBe("第 2 页");
    expect(translationBatchPageRangeText(buildBatch({ page_start: null, page_end: null }))).toBe("-");
    expect(translationBatchAttemptText(buildBatch({ attempt_count: 2, max_attempts: 0 }))).toBe("2/-");
    expect(translationBatchAiCallLogSummaryText(buildBatch({ ai_call_log_file_ids: [] }))).toBe("无关联日志");
    expect(translationBatchErrorSummaryText(buildBatch({ error_code: "translation_failed", error_message: "invalid JSON" })))
      .toBe("translation_failed: invalid JSON");
  });

  it("marks truncated or running rows with stable CSS classes and flags", () => {
    const truncated = buildBatch({ status: "split", finish_reason: "length", truncation_retry: true });

    expect(translationBatchRowClassName(truncated)).toBe("is-translation-batch-warning");
    expect(translationBatchFlagTexts(truncated)).toEqual(["已拆分", "截断重试", "finish=length"]);
    expect(translationBatchRowClassName(buildBatch({ status: "queued", retryable: true }))).toBe("is-translation-batch-warning");
    expect(translationBatchRowClassName(buildBatch({ status: "queued" }))).toBe("is-translation-batch-active");
  });

  it("summarizes counts without exposing batch content", () => {
    const summary = summarizeTranslationBatches([
      buildBatch({ status: "succeeded", item_count: 4, ai_call_log_file_ids: ["log_1"] }),
      buildBatch({ status: "failed", item_count: 8, ai_call_log_file_ids: ["log_2", "log_3"], retryable: true }),
      buildBatch({ status: "split", item_count: 0, ai_call_log_file_ids: [] }),
    ]);

    expect(summary).toMatchObject({
      total: 3,
      succeeded: 1,
      failed: 1,
      split: 1,
      attention: 2,
      itemCount: 12,
      aiCallLogCount: 3,
      providerCallBudget: 24,
      deterministicBatchCount: 2,
    });
  });
});
