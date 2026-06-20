// File: frontend/src/utils/translationQa.ts
// Purpose: Shared presentation helpers for the Translation QA drawer and future detail-page reuse.
import type {
  DocumentJobResponse,
  DocumentJobTranslationQaResponse,
  DocumentJobTranslationQaSegmentResponse,
  DocumentJobTranslationQaTermTraceResponse,
  TranslationQaIssueType,
  TranslationQaStatus,
} from "@/api/types";
import { formatDateTime } from "@/utils/format";
import { isEditableShortcutTarget } from "@/utils/keyboardShortcuts";

export type TranslationQaReviewDraft = {
  status: TranslationQaStatus;
  issue_type: TranslationQaIssueType | null;
  note: string;
};

export type TranslationQaSegmentTraceRow = DocumentJobTranslationQaSegmentResponse & {
  termTraces: DocumentJobTranslationQaTermTraceResponse[];
  termTraceCount: number;
};

export type TranslationQaDebugArchiveState = "active" | "expired" | "missing" | "off";

export const translationQaStatusOptions: TranslationQaStatus[] = ["unreviewed", "approved", "needs_fix", "blocked"];

export const translationQaIssueTypeOptions: TranslationQaIssueType[] = [
  "translation",
  "terminology",
  "layout",
  "source_quality",
  "artifact_missing",
  "other",
];

export const translationQaIssueTypeText: Record<TranslationQaIssueType, string> = {
  translation: "翻译问题",
  terminology: "术语问题",
  layout: "版式问题",
  source_quality: "源文件质量",
  artifact_missing: "证据缺失",
  other: "其他",
};

const NEXT_JOB_STATUS_PRIORITY: Record<TranslationQaStatus, number> = {
  blocked: 0,
  needs_fix: 1,
  unreviewed: 2,
  approved: 3,
};

export function buildTranslationQaSegmentRows(
  qa?: DocumentJobTranslationQaResponse | null,
): TranslationQaSegmentTraceRow[] {
  const grouped = new Map<string, DocumentJobTranslationQaTermTraceResponse[]>();
  for (const trace of qa?.term_traces || []) {
    if (!trace.segment_id) {
      continue;
    }
    const items = grouped.get(trace.segment_id) || [];
    items.push(trace);
    grouped.set(trace.segment_id, items);
  }
  return (qa?.segments || []).map((segment) => {
    const termTraces = grouped.get(segment.id) || [];
    return {
      ...segment,
      termTraces,
      termTraceCount: termTraces.length,
    };
  });
}

export function selectNextTranslationQaJob(
  jobs: DocumentJobResponse[],
  currentJobId: string,
): DocumentJobResponse | null {
  return jobs
    .filter((job) => job.id !== currentJobId)
    .map((job, index) => ({
      job,
      index,
      priority: NEXT_JOB_STATUS_PRIORITY[job.translation_qa_status] ?? Number.MAX_SAFE_INTEGER,
    }))
    .sort((left, right) => left.priority - right.priority || left.index - right.index)[0]?.job || null;
}

export function translationQaDebugArchiveState(qa?: DocumentJobTranslationQaResponse | null): TranslationQaDebugArchiveState {
  if (!qa?.summary.debug_full_text_enabled) {
    return "off";
  }
  if (!qa.artifacts.ai_debug_archive_file_ids.length) {
    return "missing";
  }
  return qa.artifacts.ai_debug_archive_expired ? "expired" : "active";
}

export function translationQaDebugArchiveStateText(state: TranslationQaDebugArchiveState): string {
  const labels: Record<TranslationQaDebugArchiveState, string> = {
    active: "可用",
    expired: "已过期",
    missing: "缺失",
    off: "未开启",
  };
  return labels[state];
}

export function translationQaDebugArchiveTagType(state: TranslationQaDebugArchiveState): "success" | "warning" | "info" {
  if (state === "active") {
    return "success";
  }
  if (state === "expired" || state === "missing") {
    return "warning";
  }
  return "info";
}

export function translationQaDebugArchiveHelper(qa?: DocumentJobTranslationQaResponse | null): string {
  const expiresAt = qa?.artifacts.ai_debug_archive_expires_at;
  if (!expiresAt) {
    return qa?.summary.debug_full_text_enabled ? "未记录过期时间" : "未保存全文归档";
  }
  return `过期时间 ${formatDateTime(expiresAt)}`;
}

export function translationQaAvailabilityReasonText(reason: string | null): string {
  const labels: Record<string, string> = {
    unsupported_mode: "当前任务不是 en2zh_pdf_to_word，翻译 QA 不适用。",
    document_ir_missing: "任务缺少 DocumentIR 证据文件，无法展示最终文本片段。",
    document_ir_unreadable: "DocumentIR 证据文件不可读取。",
  };
  return labels[reason || ""] || "翻译 QA 证据不可用。";
}

export function translationQaSourceComparisonReasonText(reason: string | null): string {
  const labels: Record<string, string> = {
    ai_debug_archive_missing: "未保存 AI debug 归档，源文/AI 译文对照不可用。",
    ai_debug_archive_expired: "AI debug 归档已过期，源文/AI 译文对照不可用。",
    ai_debug_archive_no_text: "AI debug 归档不含可展示文本，源文/AI 译文对照不可用。",
  };
  return labels[reason || ""] || "源文/AI 译文对照不可用。";
}

export function translationQaStatusCountText(value: Record<string, number>): string {
  const entries = Object.entries(value);
  return entries.length ? entries.map(([status, count]) => `${status}: ${count}`).join(", ") : "-";
}

export function translationQaPageLabel(value: number | null): string {
  return value === null ? "-" : String(value + 1);
}

export function translationQaProviderLabel(provider: Record<string, unknown>): string {
  const backend = readString(provider.backend) || "-";
  const model = readString(provider.model);
  return model ? `${backend} / ${model}` : backend;
}

export function translationQaTermTraceRangeText(trace: DocumentJobTranslationQaTermTraceResponse): string {
  if (trace.match_start === null || trace.match_end === null) {
    return "-";
  }
  return `${trace.match_start}-${trace.match_end}`;
}

export function shouldIgnoreTranslationQaShortcut(target: EventTarget | null): boolean {
  return isEditableShortcutTarget(target);
}

function readString(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value : null;
}
