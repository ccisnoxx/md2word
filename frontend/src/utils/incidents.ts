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

export type IncidentDiagnosticGuidance = {
  type: "success" | "warning" | "error" | "info";
  title: string;
  description: string;
  bullets: string[];
};

export function buildIncidentDiagnosticGuidance(item: DocumentJobIncidentQueueItemResponse): IncidentDiagnosticGuidance {
  const bullets: string[] = [];

  if (item.retryable) {
    bullets.push("后端标记为可重试，可在确认错误码和最近事件后使用现有重试动作。");
  } else {
    bullets.push(`当前不可重试：${item.retry_disabled_reason || "后端未返回可重试授权。"}`);
  }

  if (item.failure_type === "artifact_missing") {
    bullets.push("先核对文件摘要和证据入口，确认 generated_word、DocumentIR 或 QA 证据是否缺失。");
  } else if (item.failure_type === "qa_unavailable") {
    bullets.push("先打开 QA 入口或任务详情，确认 DocumentIR、AI 调用日志和 debug 归档是否可读。");
  } else if (item.failure_type === "timeout_or_stalled" || item.stalled) {
    bullets.push(`任务已停滞${item.stalled_minutes !== null ? ` ${item.stalled_minutes} 分钟` : ""}，先刷新诊断和事件再升级处理。`);
  } else if (item.failure_type === "worker_or_dispatch_failed") {
    bullets.push("优先查看最近事件中的投递、Worker 或队列错误，保留 trace_id 给技术运营。");
  }

  if (item.job.retry_count >= 3) {
    bullets.push("该任务已多次重试，请不要重复试探；先保留证据并升级给技术运营。");
  }

  if (item.blocked) {
    bullets.push("该异常已被标记为阻塞，处理前先确认上游证据或外部依赖是否恢复。");
  }

  if (item.retryable) {
    return {
      type: item.job.retry_count >= 3 ? "warning" : "success",
      title: item.job.retry_count >= 3 ? "可重试但已多次尝试" : "可按现有流程重试",
      description: "重试不会自动执行，仍需操作员确认后点击现有重试按钮。",
      bullets,
    };
  }

  return {
    type: item.stalled || item.blocked || item.failure_type === "artifact_missing" || item.failure_type === "qa_unavailable" ? "warning" : "error",
    title: "先补齐诊断证据，再决定处置",
    description: "当前抽屉只提供诊断和入口，不新增破坏性动作；需要进一步处理时打开任务详情。",
    bullets,
  };
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
