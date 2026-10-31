// 文件：frontend/src/utils/translationBatches.ts
// 用途：集中维护 document_job 翻译批次诊断与后端执行摘要的只读展示规则。
import type {
  DocumentJobTranslationBatchExecutionResponse,
  DocumentJobTranslationBatchFailureDisposition,
  DocumentJobTranslationBatchSummaryResponse,
} from "@/api/types";

export type TranslationBatchTagType = "success" | "warning" | "danger" | "info";

export type TranslationBatchSummaryCounts = {
  total: number;
  leafCount: number;
  succeeded: number;
  active: number;
  failed: number;
  split: number;
  attention: number;
  itemCount: number;
  aiCallLogCount: number;
  providerCallBudget: number | null;
  deterministicBatchCount: number | null;
  executionAvailable: boolean;
  outcome: DocumentJobTranslationBatchExecutionResponse["outcome"] | null;
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
  if (batch.failure_disposition === "superseded" || batch.is_effective_leaf === false) {
    return false;
  }
  if (batch.failure_disposition === "terminal" || batch.status === "failed") {
    return true;
  }
  if (batch.status === "split") {
    return true;
  }
  return batch.truncation_retry || batch.retryable || batch.finish_reason === "length";
}

export function translationBatchStatusTagType(batch: DocumentJobTranslationBatchSummaryResponse): TranslationBatchTagType {
  if (batch.failure_disposition === "terminal") {
    return "danger";
  }
  if (batch.failure_disposition === "retrying" || batch.failure_disposition === "stopped") {
    return "warning";
  }
  if (batch.failure_disposition === "superseded") {
    return "info";
  }
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
  if (batch.failure_disposition === "terminal") {
    return "is-translation-batch-failed";
  }
  if (batch.failure_disposition === "stopped") {
    return "is-translation-batch-stopped";
  }
  if (batch.failure_disposition === "retrying") {
    return "is-translation-batch-retrying";
  }
  if (batch.failure_disposition === "superseded") {
    return "is-translation-batch-superseded";
  }
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
  const dispositionLabels: Record<DocumentJobTranslationBatchFailureDisposition, string> = {
    none: "",
    retrying: "自动重试中",
    terminal: "终态失败",
    stopped: "其他批次已停止",
    superseded: "拆分父项",
  };
  const dispositionLabel = batch.failure_disposition ? dispositionLabels[batch.failure_disposition] : "";
  if (dispositionLabel) {
    flags.push(dispositionLabel);
  }
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

export function translationBatchDispositionText(
  batch: DocumentJobTranslationBatchSummaryResponse,
): string | null {
  if (!batch.failure_disposition) {
    return null;
  }
  const labels: Record<DocumentJobTranslationBatchFailureDisposition, string> = {
    none: "正常",
    retrying: "自动重试中",
    terminal: "终态失败",
    stopped: "其他批次已停止",
    superseded: "拆分父项",
  };
  return labels[batch.failure_disposition];
}

export function translationBatchOutcomeText(
  execution: DocumentJobTranslationBatchExecutionResponse | null | undefined,
): string | null {
  if (!execution) {
    return null;
  }
  const labels: Record<DocumentJobTranslationBatchExecutionResponse["outcome"], string> = {
    not_started: "尚未开始",
    running: "翻译进行中",
    retrying: "自动重试中",
    validating: "正在校验翻译完整性",
    failed: "翻译失败，未生成可交付 Word",
    completed: "翻译批次已完成",
    canceled: "翻译已取消",
  };
  return labels[execution.outcome];
}

export function translationBatchOutcomeTagType(
  execution: DocumentJobTranslationBatchExecutionResponse | null | undefined,
): TranslationBatchTagType {
  if (!execution) {
    return "info";
  }
  if (execution.outcome === "failed") {
    return "danger";
  }
  if (execution.outcome === "retrying") {
    return "warning";
  }
  if (execution.outcome === "completed") {
    return "success";
  }
  return "info";
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
  execution?: DocumentJobTranslationBatchExecutionResponse | null,
): TranslationBatchSummaryCounts {
  const providerBudgets = batches.map((batch) => batch.provider_call_budget).filter((value) => value > 0);
  const deterministicCounts = batches.map((batch) => batch.deterministic_batch_count).filter((value) => value > 0);
  return {
    total: batches.length,
    leafCount: execution?.leaf_count ?? batches.filter((batch) => batch.is_effective_leaf !== false && batch.status !== "split").length,
    succeeded: execution?.succeeded_leaf_count ?? batches.filter((batch) => batch.status === "succeeded" && batch.is_effective_leaf !== false).length,
    active: execution?.active_leaf_count ?? batches.filter((batch) => ACTIVE_BATCH_STATUSES.has(batch.status) && batch.is_effective_leaf !== false).length,
    failed: execution?.terminal_failed_leaf_count ?? batches.filter((batch) => batch.status === "failed" && batch.is_effective_leaf !== false).length,
    split: batches.filter((batch) => batch.status === "split").length,
    attention: batches.filter(isTranslationBatchAttention).length,
    itemCount: batches.reduce((sum, batch) => sum + batch.item_count, 0),
    aiCallLogCount: batches.reduce((sum, batch) => sum + batch.ai_call_log_file_ids.length, 0),
    providerCallBudget: providerBudgets.length ? Math.max(...providerBudgets) : null,
    deterministicBatchCount: deterministicCounts.length ? Math.max(...deterministicCounts) : null,
    executionAvailable: execution !== undefined && execution !== null,
    outcome: execution?.outcome ?? null,
  };
}
