// 文件：frontend/src/utils/format.ts
// 用途：统一任务页面使用的状态文案、展示格式和操作权限判断。
import type {
  DocumentFileResponse,
  DocumentFileSummaryResponse,
  DocumentLanguage,
  DocumentJobActionId,
  DocumentJobDisabledReason,
  DocumentJobDownloadAvailability,
  DocumentJobMode,
  DocumentJobResponse,
  DocumentJobStage,
  DocumentJobStatus,
  DocumentReviewBlockFlagResponse,
  DocumentReviewSourceSpanResponse,
  TranslationMode,
  TranslationQaStatus,
} from "@/api/types";

type DocumentJobQualityFile = DocumentFileResponse | DocumentFileSummaryResponse;

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
  translating: "翻译中",
  translation_validating: "校验翻译完整性",
  rendering: "生成 Word",
  quality_checking: "检查文档质量",
  uploading: "保存结果",
  completed: "完成",
  failed: "失败",
  canceled: "已取消",
};

export const documentJobStages = Object.keys(jobStageText) as DocumentJobStage[];

export type DocumentJobModeDefinition = {
  mode: DocumentJobMode;
  label: string;
  shortLabel: string;
  createDocumentLanguage: DocumentLanguage;
  translationMode: TranslationMode;
  requiresTranslationResources: boolean;
  supportsTranslationQa: boolean;
};

export const documentJobModeDefinitions: Record<DocumentJobMode, DocumentJobModeDefinition> = {
  direct_pdf_to_word: {
    mode: "direct_pdf_to_word",
    label: "原文 PDF 转可编辑 Word",
    shortLabel: "原文 PDF 转可编辑 Word",
    createDocumentLanguage: "auto",
    translationMode: "direct",
    requiresTranslationResources: false,
    supportsTranslationQa: false,
  },
  en2zh_pdf_to_word: {
    mode: "en2zh_pdf_to_word",
    label: "英译中",
    shortLabel: "英译中",
    createDocumentLanguage: "en",
    translationMode: "en2zh",
    requiresTranslationResources: true,
    supportsTranslationQa: true,
  },
  ru2zh_pdf_to_word: {
    mode: "ru2zh_pdf_to_word",
    label: "俄译中",
    shortLabel: "俄译中",
    createDocumentLanguage: "ru",
    translationMode: "ru2zh",
    requiresTranslationResources: true,
    supportsTranslationQa: true,
  },
  zh2en_pdf_to_word: {
    mode: "zh2en_pdf_to_word",
    label: "中译英",
    shortLabel: "中译英",
    createDocumentLanguage: "zh",
    translationMode: "zh2en",
    requiresTranslationResources: true,
    supportsTranslationQa: true,
  },
  zh2ru_pdf_to_word: {
    mode: "zh2ru_pdf_to_word",
    label: "中译俄",
    shortLabel: "中译俄",
    createDocumentLanguage: "zh",
    translationMode: "zh2ru",
    requiresTranslationResources: true,
    supportsTranslationQa: true,
  },
};

export const documentJobModeOrder: DocumentJobMode[] = [
  "direct_pdf_to_word",
  "en2zh_pdf_to_word",
  "ru2zh_pdf_to_word",
  "zh2en_pdf_to_word",
  "zh2ru_pdf_to_word",
];

export const documentJobModeOptions: DocumentJobModeDefinition[] = documentJobModeOrder.map(
  (mode) => documentJobModeDefinitions[mode],
);

export const jobModeText: Record<string, string> = {
  direct_pdf_to_word: documentJobModeDefinitions.direct_pdf_to_word.label,
  en2zh_pdf_to_word: documentJobModeDefinitions.en2zh_pdf_to_word.label,
  ru2zh_pdf_to_word: documentJobModeDefinitions.ru2zh_pdf_to_word.label,
  zh2en_pdf_to_word: documentJobModeDefinitions.zh2en_pdf_to_word.label,
  zh2ru_pdf_to_word: documentJobModeDefinitions.zh2ru_pdf_to_word.label,
};

export function documentJobModeCreateLanguage(mode: DocumentJobMode): DocumentLanguage {
  return documentJobModeDefinitions[mode].createDocumentLanguage;
}

export function documentJobModeRequiresTranslationResources(mode: DocumentJobMode): boolean {
  return documentJobModeDefinitions[mode].requiresTranslationResources;
}

export function documentJobModeTranslationMode(mode: DocumentJobMode): TranslationMode {
  return documentJobModeDefinitions[mode].translationMode;
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

export function documentJobActionDisabledReasons(job: DocumentJobResponse, action: DocumentJobActionId): DocumentJobDisabledReason[] {
  const serverAction = job.available_actions[action];
  if (serverAction?.disabled_reasons?.length) {
    return serverAction.disabled_reasons;
  }
  if (!serverAction && action === "publish") {
    return [{ code: "", message: "后端未提供发布可用性。" }];
  }
  const message = documentJobActionDisabledReason(job, action);
  return message ? [{ code: serverAction?.disabled_reason_code || "", message }] : [];
}

export function documentJobDownloadNotice(availability?: DocumentJobDownloadAvailability, isPrimaryResult = true): string {
  const classification = availability?.classification === "internal_only"
    ? "仅供内部使用"
    : isPrimaryResult ? "下载分类未提供，不能确认交付资格" : "";
  return [classification, availability?.warning_message].filter(Boolean).join("；");
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

export type DocumentJobDiagnosticRecommendation = {
  type: "success" | "warning" | "error" | "info";
  title: string;
  description: string;
  actionLabel: string;
};

export function buildDocumentJobDiagnosticRecommendation(options: {
  job: DocumentJobResponse;
  isStale?: boolean;
  callbackProblemCount?: number;
  missingResult?: boolean;
  latestErrorMessage?: string | null;
}): DocumentJobDiagnosticRecommendation {
  const { job, isStale = false, callbackProblemCount = 0, missingResult = false, latestErrorMessage = null } = options;
  const retryAction = job.available_actions.retry;
  const retryEnabled = retryAction?.enabled === true;
  const retryReason = retryAction?.disabled_reason || "后端未开放重试。";

  if (job.status === "failed") {
    return {
      type: "error",
      title: retryEnabled ? "失败任务可按后端授权重试" : "失败任务需要先确认不可重试原因",
      description: retryEnabled
        ? `后端返回重试可用。先核对失败阶段、错误码和最近错误事件，再使用现有重试动作。${latestErrorMessage ? `最近错误：${latestErrorMessage}` : ""}`.trim()
        : `后端当前不允许重试：${retryReason}。请保留错误码、阶段和 trace_id，再打开事件流或详情证据排查。`,
      actionLabel: retryEnabled ? "使用现有重试动作" : "查看事件和禁用原因",
    };
  }

  if (isStale) {
    return {
      type: "warning",
      title: "任务长时间未更新，先刷新诊断证据",
      description: "任务仍处于活跃状态，但更新时间已超过操作阈值。先刷新事件、Callback 和文件证据，再决定是否联系技术运营。",
      actionLabel: "刷新诊断",
    };
  }

  if (job.status === "succeeded") {
    if (missingResult) {
      return {
        type: "warning",
        title: "任务已完成但结果证据缺失",
        description: "后端状态已完成，但当前文件列表没有可确认的 generated_word 结果。请刷新文件证据并查看事件流。",
        actionLabel: "刷新文件证据",
      };
    }
    return {
      type: callbackProblemCount > 0 ? "warning" : "success",
      title: callbackProblemCount > 0 ? "任务已完成，但 Callback 仍有问题消息" : "任务已完成，可进入交付检查",
      description: callbackProblemCount > 0
        ? `任务结果已生成，但 Callback 摘要仍有 ${callbackProblemCount} 条问题消息。先处理 Callback 证据，再交付结果。`
        : "结果文件和质量证据可用于人工复核；下载动作仍以后端返回的可用性为准。",
      actionLabel: callbackProblemCount > 0 ? "查看 Callback 消息" : "检查质量证据",
    };
  }

  if (job.status === "canceled") {
    return {
      type: "warning",
      title: "任务已取消，保留证据用于复盘",
      description: "取消不会删除源文件、事件或已登记文件。需要复跑时使用后端允许的重新发起动作。",
      actionLabel: "查看文件和事件",
    };
  }

  return {
    type: "info",
    title: "任务处理中，等待更多证据",
    description: "页面会持续轮询任务详情。当前可先查看阶段、进度和最近事件；终态后会显示更明确的处置建议。",
    actionLabel: "继续观察",
  };
}

export function buildDocumentJobQualityEvidence(
  job: DocumentJobResponse,
  files: DocumentJobQualityFile[],
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

export function collectDocumentJobQualityFlags(files: DocumentJobQualityFile[]): string[] {
  const flags = files
    .filter((file) => file.file_type === "generated_word" || file.file_type === "document_ir")
    .flatMap((file) => {
      const qualityEvidence = readFileQualityEvidence(file);
      return [
        ...readStringArray(qualityEvidence.quality_flags),
        ...readStringArray(qualityEvidence.layout_quality_flags),
      ];
    });
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

export function documentReviewSourcePagesText(spans: DocumentReviewSourceSpanResponse[]): string {
  const pages = Array.from(new Set(spans.flatMap((span) =>
    span.source_page_index === null ? [] : [span.source_page_index + 1],
  ))).sort((left, right) => left - right);
  if (!pages.length) {
    return "源 PDF 页码未知";
  }
  const unknown = spans.some((span) => span.source_page_index === null) ? "；部分源页未知" : "";
  return `源 PDF 第 ${pages.join("、")} 页${unknown}`;
}

export function documentReviewFlagSuggestion(flag: DocumentReviewBlockFlagResponse): string {
  const suggestions: Record<string, string> = {
    caption_binding_uncertain: "题注归属尚不确定，请对照源 PDF 检查题注与图片、表格的对应关系。",
    caption_reassociated: "题注已按现有规则重新整理，可对照源 PDF 确认对应关系。",
    image_group_uncertain: "图片分组尚不确定，请对照源 PDF 检查图片、子图与题注是否完整对应。",
    formula_text_fallback: "公式使用文本回退，请对照源 PDF 检查上下标、符号和内容是否完整。",
    docx_unstyled_heading_candidates: "存在疑似未应用标题样式的内容，请检查 Word 标题层级与样式。",
    layout_caption_binding: "请对照源 PDF 检查题注与所属图片、表格的排版关系。",
    table_continuation_uncertain: "跨页表格的延续关系尚不确定，请检查各页表头与行列对应关系。",
    table_noneditable_placeholder: "表格使用不可编辑占位，请对照源 PDF 检查完整性与可编辑要求。",
  };
  const code = flag.code.split(":")[0];
  return Object.prototype.hasOwnProperty.call(suggestions, code)
    ? suggestions[code]
    : "该提示尚无专用建议，请对照源 PDF 检查此块在 Word 中的内容与排版。";
}

function selectDocumentJobFile(
  files: DocumentJobQualityFile[],
  fileType: string,
  preferredId?: string | null,
): DocumentJobQualityFile | null {
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
  resultFile: DocumentJobQualityFile | null,
  documentIrFile: DocumentJobQualityFile | null,
): DocumentJobQualityEvidenceItem[] {
  const resultMetadata = resultFile ? readFileQualityEvidence(resultFile) : {};
  const irMetadata = documentIrFile ? readFileQualityEvidence(documentIrFile) : {};
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

function readFileQualityEvidence(file: DocumentJobQualityFile): Record<string, unknown> {
  if ("quality_evidence" in file) {
    return file.quality_evidence || {};
  }
  return file.metadata || {};
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
