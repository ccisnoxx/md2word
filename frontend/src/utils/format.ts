// File: frontend/src/utils/format.ts
// Purpose: 统一任务页面使用的状态文案、展示格式和操作权限判断。
import type {
  DocumentLanguage,
  DocumentJobActionId,
  DocumentJobMode,
  DocumentJobResponse,
  DocumentJobStage,
  DocumentJobStatus,
  TranslationQaStatus,
} from "@/api/types";

export const jobStatusText: Record<DocumentJobStatus, string> = {
  pending: "等待投递",
  queued: "已入队",
  running: "处理中",
  succeeded: "已完成",
  failed: "失败",
  canceled: "已取消",
};

export const jobStageText: Record<DocumentJobStage, string> = {
  uploaded: "已上传",
  parsing: "解析 PDF",
  parsed: "解析完成",
  ir_converting: "转换文档结构",
  rendering: "生成 Word",
  uploading: "保存结果",
  completed: "完成",
  failed: "失败",
  canceled: "已取消",
};

export type DocumentJobModeDefinition = {
  mode: DocumentJobMode;
  label: string;
  shortLabel: string;
  createDocumentLanguage: DocumentLanguage;
  requiresTranslationResources: boolean;
  supportsTranslationQa: boolean;
};

export const documentJobModeDefinitions: Record<DocumentJobMode, DocumentJobModeDefinition> = {
  direct_pdf_to_word: {
    mode: "direct_pdf_to_word",
    label: "PDF 直接转 Word",
    shortLabel: "直接转 Word",
    createDocumentLanguage: "auto",
    requiresTranslationResources: false,
    supportsTranslationQa: false,
  },
  en2zh_pdf_to_word: {
    mode: "en2zh_pdf_to_word",
    label: "英文 PDF 翻译转 Word",
    shortLabel: "英译中",
    createDocumentLanguage: "en",
    requiresTranslationResources: true,
    supportsTranslationQa: true,
  },
};

export const documentJobModeOrder: DocumentJobMode[] = ["direct_pdf_to_word", "en2zh_pdf_to_word"];

export const documentJobModeOptions: DocumentJobModeDefinition[] = documentJobModeOrder.map(
  (mode) => documentJobModeDefinitions[mode],
);

export const jobModeText: Record<string, string> = {
  direct_pdf_to_word: documentJobModeDefinitions.direct_pdf_to_word.label,
  en2zh_pdf_to_word: documentJobModeDefinitions.en2zh_pdf_to_word.label,
};

export function documentJobModeCreateLanguage(mode: DocumentJobMode): DocumentLanguage {
  return documentJobModeDefinitions[mode].createDocumentLanguage;
}

export function documentJobModeRequiresTranslationResources(mode: DocumentJobMode): boolean {
  return documentJobModeDefinitions[mode].requiresTranslationResources;
}

export function documentJobModeSupportsTranslationQa(mode: DocumentJobMode): boolean {
  return documentJobModeDefinitions[mode].supportsTranslationQa;
}

export const translationQaStatusText: Record<TranslationQaStatus, string> = {
  unreviewed: "未复核",
  approved: "通过",
  needs_fix: "需修正",
  blocked: "阻塞/无法判断",
};

// 将任务级 QA 状态映射为 Element Plus tag 类型，便于列表和详情保持一致。
export function translationQaStatusTagType(status: TranslationQaStatus): "success" | "warning" | "danger" | "info" {
  if (status === "approved") {
    return "success";
  }
  if (status === "needs_fix") {
    return "warning";
  }
  if (status === "blocked") {
    return "danger";
  }
  return "info";
}

export function formatDateTime(value?: string | null): string {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(date);
}

export function formatBytes(bytes?: number | null): string {
  if (!bytes && bytes !== 0) {
    return "-";
  }
  const units = ["B", "KB", "MB", "GB"];
  let value = bytes;
  let index = 0;
  while (value >= 1024 && index < units.length - 1) {
    value /= 1024;
    index += 1;
  }
  return `${value.toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
}

export function isActiveJobStatus(status: string): boolean {
  return status === "pending" || status === "queued" || status === "running";
}

export function isArchivableJobStatus(status: string): boolean {
  return status === "succeeded" || status === "failed" || status === "canceled";
}

export function isCancelableJobStatus(status: string): boolean {
  return status === "pending" || status === "queued" || status === "running";
}

export function isArchivedDocumentJob(job: DocumentJobResponse): boolean {
  return Boolean(job.archived_at);
}

export function isDocumentJobActionEnabled(job: DocumentJobResponse, action: DocumentJobActionId): boolean {
  return job.available_actions[action]?.enabled === true;
}

export function documentJobActionDisabledReason(job: DocumentJobResponse, action: DocumentJobActionId): string {
  const serverAction = job.available_actions[action];
  if (serverAction?.disabled_reason) {
    return serverAction.disabled_reason;
  }
  return serverAction?.enabled ? "" : "后端未返回该操作的可用性。";
}

export function canDownloadDocumentJob(job: DocumentJobResponse): boolean {
  return isDocumentJobActionEnabled(job, "download");
}

export function canRetryDocumentJob(job: DocumentJobResponse): boolean {
  return isDocumentJobActionEnabled(job, "retry");
}

export function canArchiveDocumentJob(job: DocumentJobResponse): boolean {
  return isDocumentJobActionEnabled(job, "archive");
}

export function canCancelDocumentJob(job: DocumentJobResponse): boolean {
  return isDocumentJobActionEnabled(job, "cancel");
}

export function canUnarchiveDocumentJob(job: DocumentJobResponse): boolean {
  return isDocumentJobActionEnabled(job, "unarchive");
}

export function canCloneDocumentJob(job: DocumentJobResponse): boolean {
  return isDocumentJobActionEnabled(job, "clone");
}

export function getJobSourceFilename(job: DocumentJobResponse): string {
  const sourceFile = job.request_snapshot.source_file;
  if (typeof sourceFile === "object" && sourceFile !== null && "original_filename" in sourceFile) {
    const filename = sourceFile.original_filename;
    if (typeof filename === "string" && filename.trim()) {
      return filename;
    }
  }
  return job.source_file_id;
}
