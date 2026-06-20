// File: frontend/src/utils/incidents.ts
// Purpose: Shared helpers for the incident triage queue page.
import type {
  DocumentJobIncidentBulkResponse,
  DocumentJobIncidentFailureType,
  DocumentJobIncidentQueueItemResponse,
  DocumentJobIncidentRetryCountBucket,
  DocumentJobIncidentSort,
  DocumentJobStage,
  DocumentJobStatus,
} from "@/api/types";
import { isEditableShortcutTarget } from "@/utils/keyboardShortcuts";

export const incidentFailureTypes: DocumentJobIncidentFailureType[] = [
  "conversion_failed",
  "translation_failed",
  "qa_unavailable",
  "artifact_missing",
  "timeout_or_stalled",
  "worker_or_dispatch_failed",
  "unknown",
];

export const incidentSortOptions: DocumentJobIncidentSort[] = [
  "priority",
  "updated_at_desc",
  "updated_at_asc",
  "retry_count_desc",
  "retry_count_asc",
];

export const incidentRetryCountBuckets: DocumentJobIncidentRetryCountBucket[] = ["0", "1_2", "3_plus"];

export const incidentFailureTypeText: Record<DocumentJobIncidentFailureType, string> = {
  conversion_failed: "转换失败",
  translation_failed: "翻译失败",
  qa_unavailable: "QA 证据不足",
  artifact_missing: "产物缺失",
  timeout_or_stalled: "超时/停滞",
  worker_or_dispatch_failed: "Worker/投递失败",
  unknown: "未知",
};

export const incidentRetryCountBucketText: Record<DocumentJobIncidentRetryCountBucket, string> = {
  "0": "未重试",
  "1_2": "重试 1-2 次",
  "3_plus": "重试 3 次以上",
};

export const incidentSortText: Record<DocumentJobIncidentSort, string> = {
  priority: "处理优先级",
  updated_at_desc: "更新时间新到旧",
  updated_at_asc: "更新时间旧到新",
  retry_count_desc: "重试次数多到少",
  retry_count_asc: "重试次数少到多",
};

export function isIncidentFailureType(value: string): value is DocumentJobIncidentFailureType {
  return incidentFailureTypes.includes(value as DocumentJobIncidentFailureType);
}

export function isIncidentSort(value: string): value is DocumentJobIncidentSort {
  return incidentSortOptions.includes(value as DocumentJobIncidentSort);
}

export function isIncidentRetryCountBucket(value: string): value is DocumentJobIncidentRetryCountBucket {
  return incidentRetryCountBuckets.includes(value as DocumentJobIncidentRetryCountBucket);
}

export function isDocumentJobIncidentStatus(value: string): value is DocumentJobStatus {
  return ["pending", "queued", "running", "succeeded", "failed", "canceled"].includes(value);
}

export function isDocumentJobIncidentStage(value: string): value is DocumentJobStage {
  return [
    "uploaded",
    "parsing",
    "parsed",
    "ir_converting",
    "rendering",
    "uploading",
    "completed",
    "failed",
    "canceled",
  ].includes(value);
}

export function incidentFailureTagType(
  failureType: DocumentJobIncidentFailureType,
): "danger" | "warning" | "info" {
  if (failureType === "conversion_failed" || failureType === "translation_failed" || failureType === "worker_or_dispatch_failed") {
    return "danger";
  }
  if (failureType === "artifact_missing" || failureType === "timeout_or_stalled" || failureType === "qa_unavailable") {
    return "warning";
  }
  return "info";
}

export function incidentPriorityLabel(item: DocumentJobIncidentQueueItemResponse): string {
  if (item.stalled || item.blocked) {
    return "P0";
  }
  if (item.retryable) {
    return "P1";
  }
  if (item.job.status === "failed") {
    return "P2";
  }
  return "P3";
}

export function countBatchRetryable(items: DocumentJobIncidentQueueItemResponse[]): {
  retryable: number;
  nonRetryable: number;
} {
  const retryable = items.filter((item) => item.retryable).length;
  return {
    retryable,
    nonRetryable: items.length - retryable,
  };
}

export function failedOrSkippedBatchItems(result: DocumentJobIncidentBulkResponse | null) {
  return result?.items.filter((item) => !item.ok || item.skipped) || [];
}

export function shouldIgnoreIncidentShortcut(target: EventTarget | null): boolean {
  return isEditableShortcutTarget(target);
}
