// 文件：frontend/src/features/document-review/tableValueColumnReview.ts
// 用途：表格值列人工核定（replay_table_value_columns）的纯前端严格校验、载荷构造、JSON 指纹导入与后端原因码中文映射。
import type {
  DocumentQualityTableItemResponse,
  DocumentQualityTableValueFindingResponse,
  DocumentQualityUnresolvedValueColumnResponse,
  DocumentQualityValueColumnResponse,
  ManualTableValueColumnCorrectionRequest,
  ManualTableValueColumnReviewRequest,
  TableValueColumnTargetHeader,
  ValueColumnLabel,
} from "@/api/types";

export const TABLE_VALUE_TARGET_HEADERS: TableValueColumnTargetHeader[] = [
  "MIN",
  "TYP",
  "MAX",
  "NOM",
  "LOW",
  "HIGH",
];

const SHA256_HEX_RE = /^[0-9a-f]{64}$/;
const JSON_POINTER_RE = /^\/(?:content_list\/)?(?:0|[1-9][0-9]*)(?:\/(?:0|[1-9][0-9]*))?$/;

export type TableValueCorrectionDraft = {
  key: string;
  findingId: string;
  fragmentId: string;
  tableId: string;
  enabled: boolean;
  sourceRowIndex: number;
  sourceCellIndex: number | null;
  contentSha256: string;
  rangeStart: number;
  rangeEnd: number;
  targetColumn: number;
  targetHeader: TableValueColumnTargetHeader;
  valueText: string;
  unitText: string | null;
  reasonCode: string | null;
  candidateColumns: DocumentQualityValueColumnResponse[];
};

export type TableValueFragmentDraft = {
  fragmentId: string;
  tableId: string;
  pageIndex: number;
  sourcePdfSha256: string;
  contentListSha256: string;
  jsonPointer: string;
  rawHtmlSha256: string;
  corrections: TableValueCorrectionDraft[];
};

export type TableValueValidationResult = {
  valid: boolean;
  errors: string[];
  reviews: ManualTableValueColumnReviewRequest[];
};

export function normalizeHexSha256(value?: string | null): string {
  if (!value) {
    return "";
  }
  const trimmed = value.trim().toLowerCase();
  return trimmed.startsWith("sha256:") ? trimmed.slice(7) : trimmed;
}

export function mapValueColumnLabelToTargetHeader(label?: ValueColumnLabel | string | null): TableValueColumnTargetHeader {
  const upper = String(label || "").trim().toUpperCase();
  if (upper === "MIN" || upper === "最小") {
    return "MIN";
  }
  if (upper === "TYP" || upper === "典型") {
    return "TYP";
  }
  if (upper === "MAX" || upper === "最大") {
    return "MAX";
  }
  if (upper === "NOM") {
    return "NOM";
  }
  if (upper === "LOW") {
    return "LOW";
  }
  if (upper === "HIGH") {
    return "HIGH";
  }
  return "TYP";
}

// 从 /quality/tables 合并疑似数值跨列发现与未解析项，按 fragment_id 分组构建初始核定草稿。
export function buildInitialFragmentDrafts(
  tables: DocumentQualityTableItemResponse[],
  sourcePdfSha256 = "",
): TableValueFragmentDraft[] {
  const fragmentMap = new Map<string, TableValueFragmentDraft>();
  const normalizedPdf = normalizeHexSha256(sourcePdfSha256);

  function ensureFragment(fragmentId: string, tableId: string, pageIndex: number | null): TableValueFragmentDraft {
    let existing = fragmentMap.get(fragmentId);
    if (!existing) {
      existing = {
        fragmentId,
        tableId,
        pageIndex: pageIndex ?? 0,
        sourcePdfSha256: normalizedPdf,
        contentListSha256: "",
        jsonPointer: "",
        rawHtmlSha256: "",
        corrections: [],
      };
      fragmentMap.set(fragmentId, existing);
    }
    return existing;
  }

  for (const table of tables) {
    const unresolvedByFinding = new Map<string, DocumentQualityUnresolvedValueColumnResponse>();
    for (const item of table.unresolved_value_columns ?? []) {
      unresolvedByFinding.set(item.finding_id, item);
    }

    const handledFindingIds = new Set<string>();
    for (const finding of table.value_column_findings ?? []) {
      handledFindingIds.add(finding.finding_id);
      const unresolved = unresolvedByFinding.get(finding.finding_id);
      const fragment = ensureFragment(
        finding.fragment_id,
        table.table_id,
        finding.source_page_index ?? unresolved?.source_page_index ?? 0,
      );
      const firstCandidate = finding.columns[0];
      fragment.corrections.push(createCorrectionFromFinding(table.table_id, finding, unresolved, firstCandidate));
    }

    for (const unresolved of table.unresolved_value_columns ?? []) {
      if (handledFindingIds.has(unresolved.finding_id)) {
        continue;
      }
      const fragment = ensureFragment(unresolved.fragment_id, table.table_id, unresolved.source_page_index ?? 0);
      fragment.corrections.push({
        key: `${unresolved.fragment_id}:${unresolved.finding_id}`,
        findingId: unresolved.finding_id,
        fragmentId: unresolved.fragment_id,
        tableId: table.table_id,
        enabled: true,
        sourceRowIndex: unresolved.source_row_index,
        sourceCellIndex: unresolved.source_cell_index,
        contentSha256: "",
        rangeStart: 0,
        rangeEnd: 2,
        targetColumn: 0,
        targetHeader: "TYP",
        valueText: "-",
        unitText: null,
        reasonCode: unresolved.reason_code,
        candidateColumns: [],
      });
    }
  }

  return Array.from(fragmentMap.values());
}

function createCorrectionFromFinding(
  tableId: string,
  finding: DocumentQualityTableValueFindingResponse,
  unresolved: DocumentQualityUnresolvedValueColumnResponse | undefined,
  defaultCandidate: DocumentQualityValueColumnResponse | undefined,
): TableValueCorrectionDraft {
  return {
    key: `${finding.fragment_id}:${finding.finding_id}`,
    findingId: finding.finding_id,
    fragmentId: finding.fragment_id,
    tableId,
    enabled: true,
    sourceRowIndex: finding.source_row_index,
    sourceCellIndex: unresolved?.source_cell_index ?? null,
    contentSha256: "",
    rangeStart: finding.column,
    rangeEnd: finding.end_column,
    targetColumn: defaultCandidate?.column ?? finding.column,
    targetHeader: mapValueColumnLabelToTargetHeader(defaultCandidate?.label),
    valueText: finding.value,
    unitText: finding.unit,
    reasonCode: unresolved?.reason_code ?? null,
    candidateColumns: finding.columns,
  };
}

function isNonNegativeInt(value: unknown): value is number {
  return typeof value === "number" && Number.isInteger(value) && value >= 0;
}

// 严格按后端 table_value_column_review.py 规则校验并构造不含 pdf_binding 的合法载荷。
export function validateAndBuildTableValueReviews(
  fragments: TableValueFragmentDraft[],
): TableValueValidationResult {
  const errors: string[] = [];
  const reviews: ManualTableValueColumnReviewRequest[] = [];
  const seenPointers = new Set<string>();

  for (const fragment of fragments) {
    const activeCorrections = fragment.corrections.filter((item) => item.enabled);
    if (!activeCorrections.length) {
      continue;
    }

    const prefix = `片段 ${fragment.fragmentId}`;
    const sourcePdfSha256 = normalizeHexSha256(fragment.sourcePdfSha256);
    const contentListSha256 = normalizeHexSha256(fragment.contentListSha256);
    const rawHtmlSha256 = normalizeHexSha256(fragment.rawHtmlSha256);
    const jsonPointer = fragment.jsonPointer.trim();

    if (!SHA256_HEX_RE.test(sourcePdfSha256)) {
      errors.push(`${prefix}：source_pdf_sha256 必须为 64 位小写十六进制哈希。`);
    }
    if (!SHA256_HEX_RE.test(contentListSha256)) {
      errors.push(`${prefix}：content_list_sha256 必须为 64 位小写十六进制哈希。`);
    }
    if (!SHA256_HEX_RE.test(rawHtmlSha256)) {
      errors.push(`${prefix}：raw_html_sha256 必须为 64 位小写十六进制哈希。`);
    }
    if (!JSON_POINTER_RE.test(jsonPointer)) {
      errors.push(`${prefix}：json_pointer 格式无效（示例：/0/0 或 /content_list/0/0）。`);
    } else if (seenPointers.has(jsonPointer)) {
      errors.push(`${prefix}：存在重复的 json_pointer（${jsonPointer}）。`);
    } else {
      seenPointers.add(jsonPointer);
    }
    if (!isNonNegativeInt(fragment.pageIndex)) {
      errors.push(`${prefix}：page_index 必须为非负整数。`);
    }

    const seenTargets = new Set<string>();
    const builtCorrections: ManualTableValueColumnCorrectionRequest[] = [];

    for (const item of activeCorrections) {
      const rowLabel = `${prefix} 第 ${item.sourceRowIndex + 1} 行`;
      if (!isNonNegativeInt(item.sourceRowIndex)) {
        errors.push(`${rowLabel}：source_row_index 必须为非负整数。`);
      }
      if (!isNonNegativeInt(item.sourceCellIndex)) {
        errors.push(`${rowLabel}：source_cell_index 必须为非负整数。`);
      } else {
        const targetKey = `${item.sourceRowIndex}:${item.sourceCellIndex}`;
        if (seenTargets.has(targetKey)) {
          errors.push(`${rowLabel}：同一源单元格 (${item.sourceRowIndex}, ${item.sourceCellIndex}) 不能重复核定。`);
        }
        seenTargets.add(targetKey);
      }

      const cellHash = normalizeHexSha256(item.contentSha256);
      if (!SHA256_HEX_RE.test(cellHash)) {
        errors.push(`${rowLabel}：content_sha256 必须为 64 位小写十六进制哈希。`);
      }

      if (!isNonNegativeInt(item.rangeStart) || !isNonNegativeInt(item.rangeEnd) || item.rangeEnd <= item.rangeStart) {
        errors.push(`${rowLabel}：original_column_range 必须满足 0 <= 起始列 < 结束列。`);
      } else if (!isNonNegativeInt(item.targetColumn) || item.targetColumn < item.rangeStart || item.targetColumn >= item.rangeEnd) {
        errors.push(`${rowLabel}：target_column (${item.targetColumn}) 必须落在原跨列左闭右开区间 [${item.rangeStart}, ${item.rangeEnd}) 内。`);
      }

      if (!TABLE_VALUE_TARGET_HEADERS.includes(item.targetHeader)) {
        errors.push(`${rowLabel}：target_header 必须为 MIN/TYP/MAX/NOM/LOW/HIGH 之一。`);
      }

      // 严禁输出 pdf_binding 字段（后端校验器对 pdf_binding 键存在即拒绝）。
      builtCorrections.push({
        source_row_index: item.sourceRowIndex,
        source_cell_index: item.sourceCellIndex ?? 0,
        content_sha256: cellHash,
        original_column_range: [item.rangeStart, item.rangeEnd],
        target_column: item.targetColumn,
        target_header: item.targetHeader,
      });
    }

    reviews.push({
      schema_version: "table-value-column-review/v1",
      source_pdf_sha256: sourcePdfSha256,
      content_list_sha256: contentListSha256,
      page_index: fragment.pageIndex,
      json_pointer: jsonPointer,
      raw_html_sha256: rawHtmlSha256,
      normalizer_version: "table-html/v1",
      corrections: builtCorrections,
    });
  }

  if (!reviews.length) {
    errors.push("请至少勾选并核定 1 条数值跨列记录。");
  }

  return {
    valid: errors.length === 0 && reviews.length > 0,
    errors,
    reviews,
  };
}

export type ProvenanceImportResult = {
  ok: boolean;
  error?: string;
  appliedFragments: number;
  appliedCorrections: number;
};

// 解析运维工具导出的 table-value-column-review/v1 JSON（单对象或数组），自动回填指纹并拒绝含 pdf_binding 的非法输入。
export function applyProvenanceJsonToDrafts(
  rawJson: string,
  fragments: TableValueFragmentDraft[],
): ProvenanceImportResult {
  let parsed: unknown;
  try {
    parsed = JSON.parse(rawJson);
  } catch {
    return { ok: false, error: "JSON 格式解析失败，请检查括号与引号。", appliedFragments: 0, appliedCorrections: 0 };
  }

  const list = Array.isArray(parsed)
    ? parsed
    : typeof parsed === "object" && parsed !== null && "table_value_column_reviews" in parsed && Array.isArray((parsed as Record<string, unknown>).table_value_column_reviews)
      ? (parsed as { table_value_column_reviews: unknown[] }).table_value_column_reviews
      : [parsed];

  if (!list.length) {
    return { ok: false, error: "导入内容为空。", appliedFragments: 0, appliedCorrections: 0 };
  }

  for (const entry of list) {
    if (!entry || typeof entry !== "object") {
      return { ok: false, error: "导入项必须为 JSON 对象。", appliedFragments: 0, appliedCorrections: 0 };
    }
    const corrections = (entry as Record<string, unknown>).corrections;
    if (Array.isArray(corrections)) {
      for (const correction of corrections) {
        if (correction && typeof correction === "object" && "pdf_binding" in correction) {
          return {
            ok: false,
            error: "人工核定不能提交自动出处（pdf_binding），已拒绝导入。",
            appliedFragments: 0,
            appliedCorrections: 0,
          };
        }
      }
    }
  }

  let appliedFragments = 0;
  let appliedCorrections = 0;

  list.forEach((rawEntry, index) => {
    const entry = rawEntry as Record<string, unknown>;
    const fragmentId = typeof entry.fragment_id === "string" ? entry.fragment_id : "";
    const pageIndex = typeof entry.page_index === "number" ? entry.page_index : null;
    const target =
      (fragmentId && fragments.find((item) => item.fragmentId === fragmentId))
      || (pageIndex !== null && fragments.find((item) => item.pageIndex === pageIndex && !item.jsonPointer))
      || fragments[index];

    if (!target) {
      return;
    }

    appliedFragments += 1;
    if (typeof entry.source_pdf_sha256 === "string") {
      target.sourcePdfSha256 = normalizeHexSha256(entry.source_pdf_sha256);
    }
    if (typeof entry.content_list_sha256 === "string") {
      target.contentListSha256 = normalizeHexSha256(entry.content_list_sha256);
    }
    if (typeof entry.raw_html_sha256 === "string") {
      target.rawHtmlSha256 = normalizeHexSha256(entry.raw_html_sha256);
    }
    if (typeof entry.json_pointer === "string") {
      target.jsonPointer = entry.json_pointer.trim();
    }
    if (isNonNegativeInt(entry.page_index)) {
      target.pageIndex = entry.page_index;
    }

    if (Array.isArray(entry.corrections)) {
      for (const rawCorr of entry.corrections) {
        if (!rawCorr || typeof rawCorr !== "object") {
          continue;
        }
        const corr = rawCorr as Record<string, unknown>;
        const rowIndex = isNonNegativeInt(corr.source_row_index) ? corr.source_row_index : null;
        const cellIndex = isNonNegativeInt(corr.source_cell_index) ? corr.source_cell_index : null;
        const matched = target.corrections.find(
          (item) =>
            rowIndex !== null
            && item.sourceRowIndex === rowIndex
            && (item.sourceCellIndex === null || cellIndex === null || item.sourceCellIndex === cellIndex),
        );
        if (!matched) {
          continue;
        }
        appliedCorrections += 1;
        if (cellIndex !== null) {
          matched.sourceCellIndex = cellIndex;
        }
        if (typeof corr.content_sha256 === "string") {
          matched.contentSha256 = normalizeHexSha256(corr.content_sha256);
        }
        if (
          Array.isArray(corr.original_column_range)
          && corr.original_column_range.length === 2
          && isNonNegativeInt(corr.original_column_range[0])
          && isNonNegativeInt(corr.original_column_range[1])
        ) {
          matched.rangeStart = corr.original_column_range[0];
          matched.rangeEnd = corr.original_column_range[1];
        }
        if (isNonNegativeInt(corr.target_column)) {
          matched.targetColumn = corr.target_column;
        }
        if (typeof corr.target_header === "string" && TABLE_VALUE_TARGET_HEADERS.includes(corr.target_header as TableValueColumnTargetHeader)) {
          matched.targetHeader = corr.target_header as TableValueColumnTargetHeader;
        }
      }
    }
  });

  return { ok: true, appliedFragments, appliedCorrections };
}

export function tableReplayReasonLabel(reasonCode?: string | null): string {
  const map: Record<string, string> = {
    table_value_column_review_disabled: "当前租户/公司未启用表格值列同包核定试点开关。",
    table_value_column_review_mode_unsupported: "表格值列同包核定仅支持原文直转（direct）模式任务。",
    table_value_column_review_invalid: "人工核定记录未通过后端来源绑定或原格范围校验，请检查指纹与列区间。",
    table_value_column_source_unverified: "原 PDF 或 MinerU 原始结果包身份核对未通过，无法执行同包重放。",
    quality_evidence_conflict: "当前质量证据已过期或无未解析数值列，请刷新工作台后重试。",
    new_generation_source_changed: "任务当前主件或代次已变化，请刷新后重新核定。",
  };
  return reasonCode && map[reasonCode] ? map[reasonCode] : "";
}
