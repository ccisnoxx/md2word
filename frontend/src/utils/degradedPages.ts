// 文件：frontend/src/utils/degradedPages.ts
// 用途：从任务 quality_summary 的基础质量贡献中读取整页降级摘要，供详情页提示使用。

export type DegradedPageSummary = {
  page_number: number;
  trigger: "validation" | "render";
  reason_codes: string[];
};

export type SourcePageCounts = {
  source_page_count: number;
  converted_page_count: number;
  degraded_page_count: number;
  filtered_page_count: number;
  page_count_basis: "mineru_layout" | "content_blocks";
};

/** 统计的是源 PDF 页，不是 Word 页；字段不完整时不展示而非猜测。 */
export function readSourcePageCounts(qualitySummary: Record<string, unknown> | null | undefined): SourcePageCounts | null {
  const checks = qualitySummary?.checks_v1;
  const base = checks && typeof checks === "object" ? (checks as Record<string, unknown>).document_base : undefined;
  const counts = base && typeof base === "object" ? (base as Record<string, unknown>).page_counts as Record<string, unknown> | undefined : undefined;
  if (!counts || typeof counts !== "object"
    || !["source_page_count", "converted_page_count", "degraded_page_count", "filtered_page_count"].every((key) => Number.isInteger(counts[key]))
    || (counts.page_count_basis !== "mineru_layout" && counts.page_count_basis !== "content_blocks")) {
    return null;
  }
  return counts as SourcePageCounts;
}

export function sourcePageCountLine(counts: SourcePageCounts | null): string {
  if (!counts) {
    return "";
  }
  const total = `${counts.page_count_basis === "mineru_layout" ? "共" : "至少"} ${counts.source_page_count} 页`;
  const parts = [`已转换 ${counts.converted_page_count} 页`, `整页降级 ${counts.degraded_page_count} 页`];
  if (counts.filtered_page_count) {
    parts.push(`已过滤 ${counts.filtered_page_count} 页`);
  }
  return `源 PDF ${total}：${parts.join("，")}`;
}

/** quality_summary 是后端自由对象；只接受结构完整的条目，不完整时不展示而非猜测。 */
export function readDegradedPages(qualitySummary: Record<string, unknown> | null | undefined): DegradedPageSummary[] {
  const checks = qualitySummary?.checks_v1;
  const base = checks && typeof checks === "object" ? (checks as Record<string, unknown>).document_base : undefined;
  const pages = base && typeof base === "object" ? (base as Record<string, unknown>).degraded_pages : undefined;
  if (!Array.isArray(pages)) {
    return [];
  }
  return pages.filter((item): item is DegradedPageSummary => (
    !!item && typeof item === "object"
    && Number.isInteger(item.page_number) && item.page_number >= 1
    && (item.trigger === "validation" || item.trigger === "render")
    && Array.isArray(item.reason_codes) && item.reason_codes.every((code: unknown) => typeof code === "string")
  ));
}

export function degradedPageLines(pages: DegradedPageSummary[]): string[] {
  return pages.map((item) => {
    const stage = item.trigger === "render" ? "渲染" : "验证";
    const reasons = item.reason_codes.length ? item.reason_codes.join("、") : "依赖页一并降级";
    return `第 ${item.page_number} 页：${stage}阶段降级，原因 ${reasons}`;
  });
}
