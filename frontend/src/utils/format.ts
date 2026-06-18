// File: frontend/src/utils/format.ts
// Purpose: 统一任务页面使用的状态文案、展示格式和操作权限判断。
import type {
  DocumentFileResponse,
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

const ADMIN_ONLY_DOCUMENT_JOB_DELETE_REASON = "只有 admin 可以删除文档任务。";

export function shouldShowDocumentJobAction(job: DocumentJobResponse, action: DocumentJobActionId): boolean {
  const serverAction = job.available_actions[action];
  if (action !== "delete") {
    return true;
  }
  if (!serverAction) {
    return false;
  }
  return serverAction.enabled || serverAction.disabled_reason !== ADMIN_ONLY_DOCUMENT_JOB_DELETE_REASON;
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

export function canDeleteDocumentJob(job: DocumentJobResponse): boolean {
  return isDocumentJobActionEnabled(job, "delete");
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

export type DocumentJobQualityEvidenceStatus =
  | "not_ready"
  | "missing_output"
  | "manual_review_required"
  | "manual_review_required_with_flags";

export type DocumentJobQualityEvidenceItem = {
  label: string;
  value: string;
  mono?: boolean;
};

export type DocumentJobQualityEvidenceSummary = {
  status: DocumentJobQualityEvidenceStatus;
  tagType: "success" | "warning" | "danger" | "info";
  title: string;
  description: string;
  flags: string[];
  evidenceItems: DocumentJobQualityEvidenceItem[];
};

export function buildDocumentJobQualityEvidence(
  job: DocumentJobResponse,
  files: DocumentFileResponse[],
): DocumentJobQualityEvidenceSummary {
  const resultFile = selectDocumentJobFile(files, "generated_word", job.result_file_id);
  const documentIrFile = selectDocumentJobFile(files, "document_ir", job.document_ir_file_id);
  const flags = collectDocumentJobQualityFlags(files);
  const evidenceItems = buildDocumentJobQualityEvidenceItems(job, resultFile, documentIrFile);

  if (job.status !== "succeeded") {
    return {
      status: "not_ready",
      tagType: "info",
      title: "质量证据待生成",
      description: "任务未完成时，Word 质量证据以最终生成文件和 DocumentIR metadata 为准。",
      flags,
      evidenceItems,
    };
  }
  if (!resultFile) {
    return {
      status: "missing_output",
      tagType: "danger",
      title: "缺少结果文件质量证据",
      description: "任务已完成但未找到 generated_word 文件记录，请先检查文件列表和事件流。",
      flags,
      evidenceItems,
    };
  }
  if (flags.length) {
    return {
      status: "manual_review_required_with_flags",
      tagType: "warning",
      title: `需要人工复核，自动标记 ${flags.length} 项`,
      description: "后端已记录结构化质量标记，管理员复核 DOCX 时应优先检查这些版式和结构风险。",
      flags,
      evidenceItems,
    };
  }
  return {
    status: "manual_review_required",
    tagType: "warning",
    title: "需要管理员人工复核",
    description: "未发现自动质量标记；P0 Word 交付仍需管理员打开 DOCX 按 Golden Sample 标准签字。",
    flags,
    evidenceItems,
  };
}

export function collectDocumentJobQualityFlags(files: DocumentFileResponse[]): string[] {
  const flags = files
    .filter((file) => file.file_type === "generated_word" || file.file_type === "document_ir")
    .flatMap((file) => [
      ...readStringArray(file.metadata.quality_flags),
      ...readStringArray(file.metadata.layout_quality_flags),
    ]);
  return Array.from(new Set(flags));
}

export function documentJobQualityFlagText(flag: string): string {
  const code = flag.split(":")[0];
  const labels: Record<string, string> = {
    middle_json_missing: "缺少版式来源",
    layout_bbox_missing: "缺少 bbox",
    table_continuation: "跨页/延续表格",
    layout_two_column_candidate: "双栏候选",
    layout_wide_table: "宽表",
    layout_caption_binding: "标题绑定",
    layout_footnote_binding: "脚注绑定",
    missing_image_asset: "图片资产缺失",
    empty_content_list: "解析内容为空",
    unsupported_block_type: "不支持的块类型",
    docx_quality_unavailable: "DOCX 质量证据不可用",
    docx_analysis_error: "DOCX 结构分析失败",
    docx_no_editable_content: "缺少可编辑内容",
    docx_image_only_suspected: "疑似整页截图",
    docx_latex_residue: "LaTeX 残留",
    docx_manual_list_markers: "手写列表符号",
    docx_plain_toc_entries: "纯文本目录项",
    docx_unstyled_heading_candidates: "疑似标题未样式化",
    docx_wide_table_without_landscape: "宽表未横版",
  };
  return labels[code] ? `${labels[code]} · ${flag}` : flag;
}

function selectDocumentJobFile(
  files: DocumentFileResponse[],
  fileType: string,
  preferredId?: string | null,
): DocumentFileResponse | null {
  if (preferredId) {
    const preferred = files.find((file) => file.id === preferredId && file.file_type === fileType);
    if (preferred) {
      return preferred;
    }
  }
  return files.find((file) => file.file_type === fileType) || null;
}

function buildDocumentJobQualityEvidenceItems(
  job: DocumentJobResponse,
  resultFile: DocumentFileResponse | null,
  documentIrFile: DocumentFileResponse | null,
): DocumentJobQualityEvidenceItem[] {
  const resultMetadata: Record<string, unknown> = resultFile?.metadata || {};
  const irMetadata: Record<string, unknown> = documentIrFile?.metadata || {};
  const docxQuality = readRecord(resultMetadata.docx_quality);
  const items: DocumentJobQualityEvidenceItem[] = [];
  addEvidenceItem(items, "结果文件", resultFile?.id || job.result_file_id, true);
  addEvidenceItem(items, "DocumentIR", documentIrFile?.id || job.document_ir_file_id, true);
  addEvidenceItem(items, "Schema", readString(resultMetadata.schema_version) || readString(irMetadata.schema_version), true);
  addEvidenceItem(items, "Renderer", readString(resultMetadata.renderer_mode), true);
  addEvidenceItem(items, "Layout pages", readDisplayValue(resultMetadata.layout_page_count ?? irMetadata.layout_page_count), true);
  addEvidenceItem(items, "Layout blocks", readDisplayValue(resultMetadata.layout_block_count ?? irMetadata.layout_block_count), true);
  addEvidenceItem(items, "可编辑内容", readBooleanDisplayValue(docxQuality.editable_content_available), true);
  addEvidenceItem(items, "疑似整页截图", readBooleanDisplayValue(docxQuality.image_only_suspected), true);
  addEvidenceItem(items, "Heading", readDisplayValue(docxQuality.heading_paragraphs), true);
  addEvidenceItem(items, "疑似标题", readDisplayValue(docxQuality.heading_like_unstyled_paragraphs), true);
  addEvidenceItem(items, "Numbering", readDisplayValue(docxQuality.numbering_paragraphs), true);
  addEvidenceItem(items, "手写列表", readDisplayValue(docxQuality.manual_list_marker_paragraphs), true);
  addEvidenceItem(items, "TOC tabs", readDisplayValue(docxQuality.toc_tab_leader_paragraphs), true);
  addEvidenceItem(items, "纯文本目录", readDisplayValue(docxQuality.plain_toc_entry_paragraphs), true);
  addEvidenceItem(items, "表格", readDisplayValue(docxQuality.table_count), true);
  addEvidenceItem(items, "宽表", readDisplayValue(docxQuality.wide_table_count), true);
  addEvidenceItem(items, "表头重复", readDisplayValue(docxQuality.table_header_rows), true);
  addEvidenceItem(items, "表格防断行", readDisplayValue(docxQuality.table_no_split_rows), true);
  addEvidenceItem(items, "LaTeX 残留", readDisplayValue(docxQuality.latex_residue_count), true);
  addEvidenceItem(items, "Template", readString(resultMetadata.template_version_id) || job.template_version_id, true);
  return items;
}

function addEvidenceItem(
  items: DocumentJobQualityEvidenceItem[],
  label: string,
  value: string | null | undefined,
  mono = false,
): void {
  if (!value) {
    return;
  }
  items.push({ label, value, mono });
}

function readStringArray(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value.filter((item): item is string => typeof item === "string" && Boolean(item.trim()));
  }
  if (typeof value === "string" && value.trim()) {
    return [value];
  }
  return [];
}

function readString(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value : null;
}

function readRecord(value: unknown): Record<string, unknown> {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }
  return {};
}

function readBooleanDisplayValue(value: unknown): string | null {
  if (typeof value === "boolean") {
    return value ? "是" : "否";
  }
  return null;
}

function readDisplayValue(value: unknown): string | null {
  if (typeof value === "string" && value.trim()) {
    return value;
  }
  if (typeof value === "number" && Number.isFinite(value)) {
    return String(value);
  }
  return null;
}
