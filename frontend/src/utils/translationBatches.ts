// File: frontend/src/utils/translationBatches.ts
// Purpose: Shared display helpers for read-only document_job translation provider batch diagnostics.
import type { DocumentJobTranslationBatchSummaryResponse } from "@/api/types";

export type TranslationBatchTagType = "success" | "warning" | "danger" | "info";

export type TranslationBatchSummaryCounts = {
  total: number;
  succeeded: number;
  active: number;
  failed: number;
  split: number;
  attention: number;
  itemCount: number;
  aiCallLogCount: number;
  providerCallBudget: number | null;
  deterministicBatchCount: number | null;
};

const ACTIVE_BATCH_STATUSES = new Set(["pending", "queued", "running"]);

export function translationBatchStatusText(status: string): string {
  const labels: Record<string, string> = {
    pending: "待执行",
    queued: "已入队",
    running: "运行中",
    succeeded: "成功",
    failed: "失败",
    split: "已拆分",
    canceled: "已取消",
  };
  return labels[status] || status;
}

export function isTranslationBatchAttention(batch: DocumentJobTranslationBatchSummaryResponse): boolean {
  if (batch.status === "failed" || batch.status === "split") {
    return true;
  }
  return batch.truncation_retry || batch.retryable || batch.finish_reason === "length";
}

export function translationBatchStatusTagType(batch: DocumentJobTranslationBatchSummaryResponse): TranslationBatchTagType {
  if (batch.status === "failed") {
    return "danger";
  }
  if (batch.status === "succeeded" && !isTranslationBatchAttention(batch)) {
    return "success";
  }
  if (batch.status === "split" || batch.status === "canceled" || isTranslationBatchAttention(batch)) {
    return "warning";
  }
  return "info";
}

export function translationBatchRowClassName(batch: DocumentJobTranslationBatchSummaryResponse): string {
  if (batch.status === "failed") {
    return "is-translation-batch-failed";
  }
  if (
    batch.status === "split"
    || batch.truncation_retry
    || batch.finish_reason === "length"
    || (batch.retryable && batch.status !== "succeeded")
  ) {
    return "is-translation-batch-warning";
  }
  if (ACTIVE_BATCH_STATUSES.has(batch.status)) {
    return "is-translation-batch-active";
  }
  return "";
}

export function translationBatchFlagTexts(batch: DocumentJobTranslationBatchSummaryResponse): string[] {
  const flags: string[] = [];
  if (batch.status === "split") {
    flags.push("已拆分");
  }
  if (batch.truncation_retry) {
    flags.push("截断重试");
  }
  if (batch.finish_reason === "length") {
    flags.push("finish=length");
  }
  if (batch.retryable && batch.status !== "succeeded") {
    flags.push("可重试");
  }
  return flags;
}

export function translationBatchPageRangeText(batch: DocumentJobTranslationBatchSummaryResponse): string {
  if (batch.page_start === null || batch.page_end === null) {
    return "-";
  }
  if (batch.page_start === batch.page_end) {
    return `第 ${batch.page_start} 页`;
  }
  return `第 ${batch.page_start}-${batch.page_end} 页`;
}

export function translationBatchScaleText(batch: DocumentJobTranslationBatchSummaryResponse): string {
  const charText = batch.char_count > 0 ? ` / ${batch.char_count} chars` : "";
  return `${batch.item_count} items${charText}`;
}

export function translationBatchAttemptText(batch: DocumentJobTranslationBatchSummaryResponse): string {
  const maxAttempts = batch.max_attempts > 0 ? String(batch.max_attempts) : "-";
  return `${batch.attempt_count}/${maxAttempts}`;
}

export function translationBatchErrorSummaryText(batch: DocumentJobTranslationBatchSummaryResponse): string {
  if (batch.error_code && batch.error_message) {
    return `${batch.error_code}: ${batch.error_message}`;
  }
  return batch.error_code || batch.error_message || "-";
}

export function translationBatchAiCallLogSummaryText(batch: DocumentJobTranslationBatchSummaryResponse): string {
  const count = batch.ai_call_log_file_ids.length;
  if (!count) {
    return "无关联日志";
  }
  return `${count} 个日志`;
}

export function translationBatchFileIdsText(fileIds: string[]): string {
  return fileIds.length ? fileIds.join(", ") : "-";
}

export function summarizeTranslationBatches(
  batches: DocumentJobTranslationBatchSummaryResponse[],
): TranslationBatchSummaryCounts {
  const providerBudgets = batches.map((batch) => batch.provider_call_budget).filter((value) => value > 0);
  const deterministicCounts = batches.map((batch) => batch.deterministic_batch_count).filter((value) => value > 0);
  return {
    total: batches.length,
    succeeded: batches.filter((batch) => batch.status === "succeeded").length,
    active: batches.filter((batch) => ACTIVE_BATCH_STATUSES.has(batch.status)).length,
    failed: batches.filter((batch) => batch.status === "failed").length,
    split: batches.filter((batch) => batch.status === "split").length,
    attention: batches.filter(isTranslationBatchAttention).length,
    itemCount: batches.reduce((sum, batch) => sum + batch.item_count, 0),
    aiCallLogCount: batches.reduce((sum, batch) => sum + batch.ai_call_log_file_ids.length, 0),
    providerCallBudget: providerBudgets.length ? Math.max(...providerBudgets) : null,
    deterministicBatchCount: deterministicCounts.length ? Math.max(...deterministicCounts) : null,
  };
}
