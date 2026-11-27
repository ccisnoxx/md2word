// 文件：frontend/src/features/document-review/documentReviewFormat.ts
// 用途：统一文档复核工作台与发布面板的中文语义映射、定位诚实表达与来源摘要工具。
import type {
  DocumentJobMode,
  DocumentJobReviewStatus,
  DocumentPreviewResponse,
  DocumentQualitySourceResponse,
  DocumentReviewBlockItemResponse,
  DocumentReviewLocationResponse,
  DocumentReviewTokenCountsResponse,
  DocumentReviewValidityReason,
  QualityIssue,
  QualityRule,
  ReviewExpectedSourceRequest,
} from "@/api/types";
import { documentJobModeTranslationMode } from "@/utils/format";

export const reviewStatusOptions: DocumentJobReviewStatus[] = [
  "approved",
  "needs_fix",
  "blocked",
  "unreviewed",
];

export const reviewIssueTypeOptions: QualityIssue[] = [
  "conversion",
  "translation",
  "terminology",
  "table_structure",
  "layout",
  "source_quality",
  "artifact_missing",
  "other",
];

export const reviewIssueTypeText: Record<QualityIssue, string> = {
  conversion: "转换解析问题",
  translation: "翻译质量问题",
  terminology: "术语不一致",
  table_structure: "表格结构/数值列归属",
  layout: "版式排版问题",
  source_quality: "源 PDF 质量缺陷",
  artifact_missing: "产物或证据缺失",
  other: "其他问题",
};

export const reviewBlockTypeOptions: Array<{
  value: DocumentReviewBlockItemResponse["block_type"];
  label: string;
}> = [
  { value: "heading", label: "标题" },
  { value: "paragraph", label: "段落" },
  { value: "table", label: "表格" },
  { value: "formula", label: "公式" },
  { value: "list", label: "列表" },
  { value: "image", label: "图片" },
];

export const reviewBlockTypeText: Record<DocumentReviewBlockItemResponse["block_type"], string> = {
  heading: "标题",
  paragraph: "段落",
  table: "表格",
  formula: "公式",
  list: "列表",
  image: "图片",
};

export const reviewValidityReasonText: Record<DocumentReviewValidityReason, string> = {
  legacy_unbound: "历史复核记录未绑定当前主件摘要，需针对当前代次重新复核。",
  source_changed: "任务产物或代次已变化，先前复核记录已失效，需重新确认。",
  artifact_missing: "当前主件文件或质量收据缺失，复核结论无法生效。",
  artifact_unavailable: "当前产物校验暂时不可用，请刷新后再确认复核状态。",
  integrity_conflict: "主件完整性校验与登记记录冲突，需重新核验。",
  quality_blocked: "当前存在阻断级质量标记，历史批准自动失效。",
  table_semantics_confirmation_required: "表格报告包含疑似数值跨列发现，批准前必须勾选确认已核对表格语义归属报告。",
  table_semantics_confirmation_stale: "表格语义归属报告摘要已更新，批准前需重新勾选确认最新报告。",
  table_semantics_evidence_invalid: "表格语义归属证据校验异常，当前无法确认语义报告摘要。",
};

export function isTableSemanticsConflictReason(reason?: DocumentReviewValidityReason | null): boolean {
  return (
    reason === "table_semantics_confirmation_required"
    || reason === "table_semantics_confirmation_stale"
    || reason === "table_semantics_evidence_invalid"
  );
}

export function reviewValidityReasonLabel(reason?: DocumentReviewValidityReason | null): string {
  if (!reason) {
    return "";
  }
  return reviewValidityReasonText[reason] || `复核有效性提示（${reason}）`;
}

export const qualityRuleText: Record<QualityRule, string> = {
  clipping: "裁切风险",
  overflow: "越界溢出",
  blank: "疑似空白页",
  overlap: "元素重叠",
  density: "版面密度",
};

export const pageFlagText: Record<string, string> = {
  page_clip_risk: "页面边缘疑似裁切",
  page_overflow_risk: "内容疑似越界溢出",
  unexpected_blank_page_suspected: "疑似异常空白页",
  page_overlap_suspected: "文本或图形疑似重叠",
  page_density_low: "页面内容密度偏低",
  page_density_high: "页面内容密度偏高",
};

export const tableRenderStateText: Record<string, string> = {
  native: "原生可编辑表格",
  placeholder: "不可编辑图片占位",
  mixed: "原生与占位混合",
  excluded_margin_artifact: "已排除页边噪声",
};

export const tableUnresolvedReasonText: Record<string, string> = {
  source_pair_unverified: "源页配对未认证",
  layout_unverified: "版面坐标未认证",
  table_layout_unverified: "表格几何布局未认证",
  table_region_ambiguous: "表格区域存在歧义",
  unsupported_table_shape: "复杂表格结构暂不支持自动绑定",
  unsupported_cell_shape: "复杂单元格合并暂不支持自动绑定",
  unsupported_pdf_geometry: "PDF 几何坐标暂不支持",
  pdf_source_unavailable: "源 PDF 文件不可用",
  pdf_geometry_unverified: "PDF 几何信息未认证",
  pdf_text_unavailable: "PDF 文本层不可用",
  pdf_observation_unavailable: "PDF 观测结果不可用",
  pdf_observation_budget_exhausted: "PDF 观测预算已耗尽",
  header_ambiguous: "表头列语义存在歧义",
  row_ambiguous: "数据行匹配存在歧义",
  column_ambiguous: "数值列归属存在歧义",
  value_ambiguous: "单元格数值匹配存在歧义",
  row_anchor_missing: "缺少行锚点",
  row_anchor_nonunique: "行锚点不唯一",
  rowspan_context_unresolved: "跨行上下文未解析",
  value_word_nonunique: "同行重复数值词无法唯一消歧",
  unit_row_mismatch: "单位与行不匹配",
  source_row_band_count_mismatch: "源表行带数量不一致",
  row_sequence_ambiguous: "行序存在歧义",
  value_visibility_unverified: "数值可见性未认证",
  span_contains_other_content: "跨列范围包含其他内容",
  unit_mismatch: "单位不一致",
  competing_pdf_binding: "存在多个竞争的 PDF 列绑定",
};

export function tableUnresolvedReasonLabel(reasonCode: string): string {
  return tableUnresolvedReasonText[reasonCode] || `待人工核定（${reasonCode}）`;
}

export const previewStatusText: Record<DocumentPreviewResponse["status"], string> = {
  not_ready: "尚未就绪",
  disabled: "预览未启用",
  pending: "排队渲染中",
  running: "正在生成预览",
  succeeded: "预览就绪",
  failed: "预览渲染失败",
  unavailable: "预览暂不可用",
};

export function previewReasonLabel(reasonCode?: string | null, status?: DocumentPreviewResponse["status"]): string {
  const map: Record<string, string> = {
    preview_disabled: "当前环境未开启 Word 页级预览生成功能。",
    not_ready: "任务尚未生成最终 Word 结果或预览尚未完成。",
    preview_not_ready: "Word 页级预览尚未生成完成，请稍后刷新。",
    preview_failed: "Word 转预览 PNG 渲染失败，建议下载内部草稿 DOCX 在本地 Word 中核对。",
    preview_unavailable: "预览存储或预览产物暂不可用，请下载内部草稿 DOCX 在本地核对。",
    legacy_unavailable: "该历史任务生成时未登记页级预览产物。",
    libreoffice_unavailable: "服务端预览转换组件当前不可用。",
  };
  if (reasonCode && map[reasonCode]) {
    return map[reasonCode];
  }
  if (status === "disabled") {
    return map.preview_disabled;
  }
  if (status === "failed") {
    return map.preview_failed;
  }
  if (status === "pending" || status === "running") {
    return "Word 预览正在后台生成中，可稍后点击刷新查看。";
  }
  if (status === "not_ready") {
    return map.not_ready;
  }
  return reasonCode ? `预览暂不可用（原因码：${reasonCode}）。建议打开源 PDF 或下载内部草稿 DOCX 在本地核对。` : "当前无法显示 Word 预览页，建议打开源 PDF 或下载内部草稿 DOCX 在本地核对。";
}

export type ReviewLocationBadge = {
  label: string;
  tagType: "success" | "warning" | "info";
  detail: string;
};

// 严格按后端 location.kind 与 confidence 表达映射可靠性，绝不拿源 PDF 页码冒充 Word 页码。
export function formatReviewLocationBadge(location?: DocumentReviewLocationResponse | null): ReviewLocationBadge {
  if (!location) {
    return { label: "未定位", tagType: "info", detail: "当前未选中文档块。" };
  }
  const dispositionMap: Record<string, string> = {
    rendered: "已渲染",
    coalesced: "已合并渲染",
    suppressed: "已抑制未输出",
    superseded: "已被后续块替代",
    not_emitted: "未输出到 Word",
  };
  const dispositionText = location.disposition ? dispositionMap[location.disposition] || location.disposition : "";
  const confidenceText = location.confidence === "high" ? "高置信" : location.confidence === "low" ? "低置信" : "无置信度";

  if (location.kind === "single_page" && location.preview_page_index !== null) {
    return {
      label: `Word 第 ${location.preview_page_index + 1} 页 · 精确页映射（${confidenceText}）`,
      tagType: location.confidence === "high" ? "success" : "warning",
      detail: [dispositionText, location.bookmark_label ? `书签：${location.bookmark_label}` : ""].filter(Boolean).join(" · "),
    };
  }
  if (location.kind === "estimated_start" && location.preview_page_index !== null) {
    return {
      label: `Word 第 ${location.preview_page_index + 1} 页起 · 估算起页（${confidenceText}）`,
      tagType: "warning",
      detail: [dispositionText, "该块可能跨页或按邻近锚点估算，请结合前后页核对"].filter(Boolean).join(" · "),
    };
  }
  const fallbackText = location.fallback_page_index !== null
    ? `参考相近 Word 第 ${location.fallback_page_index + 1} 页（不代表该块精确落页）`
    : "未获得 Word 预览页映射（源 PDF 页码不等于 Word 实际页码）";
  return {
    label: "Word 页映射不可用",
    tagType: "info",
    detail: [dispositionText, fallbackText, location.reason_code ? `原因：${location.reason_code}` : ""].filter(Boolean).join(" · "),
  };
}

export const tokenCategoryText: Record<keyof DocumentReviewTokenCountsResponse, string> = {
  formula: "公式",
  literal_placeholder: "字面占位",
  address: "寄存器/地址",
  bit_field: "位域",
  model: "器件型号",
  standard: "标准号",
  version: "版本号",
  signal: "信号名",
  quantity: "物理量",
  unit: "单位",
  url: "链接",
  email: "邮箱",
  number: "数值",
  symbol: "符号",
  technical_literal: "技术字面量",
};

export const publicationPreflightCodeText: Record<string, string> = {
  result_download: "结果主件可下载校验",
  admin_role: "管理员发布权限",
  template_binding: "模板发布资格",
  quality: "自动质量检查结论",
  review: "人工复核批准结论",
  publication_state: "当前代次未重复发布",
  publication_write: "系统发布写入开关",
  job_state: "任务未归档/未删除",
  publication_evidence: "预览、实物完整性与快照证据",
};

export function publicationPreflightTitle(code: string): string {
  return publicationPreflightCodeText[code] || code;
}

export function buildExpectedSource(source: DocumentQualitySourceResponse): ReviewExpectedSourceRequest {
  return {
    generation: source.generation,
    result_file_id: source.result_file_id,
    result_sha256: source.result_sha256,
    file_review_source_revision: source.file_review_source_revision,
    receipt_sha256: source.receipt_sha256,
  };
}

export function shortHash(value?: string | null, length = 12): string {
  if (!value) {
    return "-";
  }
  const cleaned = value.startsWith("sha256:") ? value.slice(7) : value;
  if (cleaned.length <= length) {
    return cleaned;
  }
  return `${cleaned.slice(0, length)}…`;
}

export function languagePairFromJobMode(mode?: DocumentJobMode | null): string | null {
  if (!mode) {
    return null;
  }
  const translationMode = documentJobModeTranslationMode(mode);
  if (translationMode === "direct") {
    return null;
  }
  return translationMode;
}
