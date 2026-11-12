// 文件管理页的无状态映射：状态标签、安全标记与 unknown 报告字段读取。
import type {
  FileRetentionCleanupRunHistoryStatus,
  FileRetentionDeleteItemResponse,
  FileRetentionDeleteOutcome,
} from "@/api/types";

export type StatusTag = "success" | "warning" | "info" | "danger";

export type UnknownRecord = Record<string, unknown>;

export const fileTypeOptions = [
  "source_pdf",
  "mineru_raw_result",
  "document_ir",
  "image_asset",
  "generated_word",
  "ai_call_log",
  "ai_debug_archive",
  "template_docx",
  "template_config",
  "term_file",
];

export const schedulerExpectedTrueSafety = new Set([
  "scheduler_manual_dry_run_executed",
  "cleanup_lock_acquired",
  "cleanup_lock_released",
  "history_recorded",
]);

export const schedulerUnsafeTrueSafety = new Set([
  "scheduler_loop_executed",
  "metadata_mutated",
  "objects_deleted",
  "mark_expired_executed",
  "physical_delete_executed",
  "provider_calls_executed",
  "s3_delete_executed",
  "audit_events_written",
]);

// 将 ratio 小数转换为百分比展示；未配置 quota 时展示短横线。
export function formatRatio(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return "-";
  }
  return `${(value * 100).toFixed(1)}%`;
}

// 仅把普通对象视为可读记录，避免从 unknown report 里误读数组或 null。
export function asRecord(value: unknown): UnknownRecord | null {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    return null;
  }
  return value as UnknownRecord;
}

// 从 unknown record 中读取数值字段，非数字字段按缺失处理。
export function numberField(record: UnknownRecord | null, key: string): number | null {
  const value = record?.[key];
  return typeof value === "number" ? value : null;
}

// 将 scheduler dry-run safety flag 映射为标签样式，突出任何意外副作用。
export function schedulerDryRunSafetyTag(label: string, value: boolean): StatusTag {
  if (value && schedulerUnsafeTrueSafety.has(label)) {
    return "danger";
  }
  if (!value && schedulerExpectedTrueSafety.has(label)) {
    return "danger";
  }
  if (value) {
    return "success";
  }
  return "info";
}

// 将 metadata 状态映射为表格标签样式。
export function statusTag(status: string): StatusTag {
  if (status === "uploaded") {
    return "warning";
  }
  if (status === "expired") {
    return "info";
  }
  if (status === "deleted") {
    return "danger";
  }
  return "success";
}

// 将 policy 状态映射为标签样式。
export function policyStatusTag(status: string): StatusTag {
  if (status === "draft") {
    return "warning";
  }
  if (status === "published") {
    return "success";
  }
  if (status === "disabled") {
    return "info";
  }
  return "info";
}

// 将 advisory quota 状态映射为标签样式。
export function storageQuotaStatusTag(status: string): StatusTag {
  if (status === "exceeded") {
    return "danger";
  }
  if (status === "warning") {
    return "warning";
  }
  if (status === "ok") {
    return "success";
  }
  return "info";
}

// 将 quota policy dry-run 状态映射为标签样式。
export function quotaPolicyStatusTag(status: string): StatusTag {
  if (status === "dry_run" || status === "ready") {
    return "success";
  }
  if (status === "invalid") {
    return "danger";
  }
  if (status === "not_configured") {
    return "warning";
  }
  return "info";
}

// 将 quota enforcement readiness 映射为运维状态标签。
export function quotaOpsReadinessTag(enforcementReady: boolean): StatusTag {
  return enforcementReady ? "success" : "warning";
}

// 将 quota audit replay outcome 映射为结果标签样式。
export function quotaAuditOutcomeTag(outcome: string | null): StatusTag {
  if (outcome === "blocked") {
    return "danger";
  }
  if (outcome === "overridden") {
    return "warning";
  }
  if (outcome === "allowed") {
    return "success";
  }
  return "info";
}

// 将 cleanup run history 状态映射为标签样式。
export function cleanupHistoryStatusTag(status: FileRetentionCleanupRunHistoryStatus): StatusTag {
  if (status === "executed") {
    return "success";
  }
  if (status === "failed") {
    return "danger";
  }
  if (status === "dry_run") {
    return "info";
  }
  return "warning";
}

// 将物理删除 outcome 映射为结果标签样式。
export function outcomeTag(outcome: FileRetentionDeleteOutcome): StatusTag {
  if (outcome === "deleted" || outcome === "already_missing" || outcome === "deletable") {
    return "success";
  }
  if (outcome === "failed") {
    return "danger";
  }
  if (outcome === "skipped_unsupported_storage") {
    return "warning";
  }
  return "info";
}

// 展示 S3 fake deletion contract 的关键安全结论，避免误解为真实删除。
export function s3ContractLabel(row: FileRetentionDeleteItemResponse): string {
  const contract = row.s3_delete_contract;
  if (!contract) {
    return "-";
  }
  const target = contract.target_exact ? "exact" : "inexact";
  const realDelete = contract.safety.real_s3_delete_executed ? "real-delete" : "no-real-delete";
  return `${contract.adapter_mode}/${target}/${realDelete}`;
}
