// frontend/src/utils/format.ts: Shared labels and formatting helpers for job pages.
import type { DocumentJobStage, DocumentJobStatus } from "@/api/types";

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

export const jobModeText: Record<string, string> = {
  direct_pdf_to_word: "PDF 直接转 Word",
  en2zh_pdf_to_word: "英文 PDF 翻译转 Word",
};

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
