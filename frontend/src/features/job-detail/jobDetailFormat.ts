import type {
  DocumentFileSummaryResponse,
  DocumentJobResourceSnapshot,
  DocumentJobResponse,
  DocumentJobTranslationBatchSummaryResponse,
} from "@/api/types";
import { documentJobModeRequiresTranslationResources, documentJobModeSupportsTranslationQa } from "@/utils/format";
import { translationBatchRowClassName } from "@/utils/translationBatches";

export function supportsJobTranslationQa(target: DocumentJobResponse | null | undefined): boolean {
  return Boolean(target && documentJobModeSupportsTranslationQa(target.mode));
}

export function usesTranslationResources(target: DocumentJobResponse | null | undefined): boolean {
  return Boolean(target && documentJobModeRequiresTranslationResources(target.mode));
}

export function readRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === "object" && value !== null ? value as Record<string, unknown> : null;
}

export function readString(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value : null;
}

export function readResourceSnapshot(value: unknown): DocumentJobResourceSnapshot | null {
  return readRecord(value) as DocumentJobResourceSnapshot | null;
}

export function versionLabel(setId?: string | null, version?: string | null): string {
  const normalizedSetId = setId || "-";
  const normalizedVersion = version || "-";
  return normalizedSetId === "-" && normalizedVersion === "-" ? "-" : `${normalizedSetId}@${normalizedVersion}`;
}

export function parseDate(value?: string | null): Date | null {
  if (!value) {
    return null;
  }
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

export function secondsLabel(value: number | null): string {
  if (value === null) {
    return "-";
  }
  return `${value} 秒`;
}

// 文件区只做展示映射；文件归属、过期和下载权限以后端校验为准。
export function fileRoleText(fileType: string): string {
  if (fileType === "source_pdf") {
    return "源文件";
  }
  if (fileType === "generated_word") {
    return "结果";
  }
  if (fileType === "ai_call_log" || fileType === "ai_debug_archive") {
    return "日志";
  }
  return "中间产物";
}

export function fileTypeText(fileType: string): string {
  const labels: Record<string, string> = {
    source_pdf: "源 PDF",
    generated_word: "生成 Word",
    mineru_raw_result: "MinerU 原始结果",
    document_ir: "DocumentIR",
    image_asset: "图片资产",
    image_assets_archive: "图片资源包",
    ai_call_log: "AI 调用日志",
    ai_debug_archive: "AI 调试归档",
  };
  return labels[fileType] || fileType;
}

export function fileTagType(fileType: string): "success" | "warning" | "info" {
  if (fileType === "generated_word") {
    return "success";
  }
  if (fileType === "ai_call_log" || fileType === "ai_debug_archive") {
    return "warning";
  }
  return "info";
}

function isFileExpired(file: DocumentFileSummaryResponse): boolean {
  const expiresAt = parseDate(file.expires_at);
  return Boolean(expiresAt && expiresAt.getTime() <= Date.now());
}

export function canDownloadFile(file: DocumentFileSummaryResponse): boolean {
  return file.status === "uploaded" && !isFileExpired(file);
}

export function fileAvailabilityText(file: DocumentFileSummaryResponse): string {
  if (file.status !== "uploaded") {
    return file.status;
  }
  if (isFileExpired(file)) {
    return "已过期";
  }
  return "可下载";
}

export function translationBatchTableRowClassName({ row }: { row: DocumentJobTranslationBatchSummaryResponse }): string {
  return translationBatchRowClassName(row);
}
