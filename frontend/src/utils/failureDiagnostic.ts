import type { DocumentJobFailureDiagnostic } from "@/api/types";

/** 详情页失败摘要与异常中心抽屉共用的定位文案；后端未给出页码时不推测页码。 */
export function failureDiagnosticLines(diagnostic: DocumentJobFailureDiagnostic | null | undefined): string[] {
  if (!diagnostic) {
    return [];
  }
  const location = diagnostic.source === "render_operation"
    ? [diagnostic.block_ids?.length ? `块 ${diagnostic.block_ids.join("、")}` : null,
      diagnostic.operation_kind ? `操作 ${diagnostic.operation_kind}` : null].filter(Boolean).join("，")
    : [diagnostic.source_type, diagnostic.json_pointer].filter(Boolean).join("，");
  const lines = [
    diagnostic.scope === "page" && diagnostic.page_number !== null
      ? `首个失败位置：第 ${diagnostic.page_number} 页${location ? `（${location}）` : ""}`
      : `首个失败位置：文档级问题，无法定位到单页${diagnostic.source === "render_operation" && location ? `（${location}）` : ""}`,
    `原因：${diagnostic.reason_code}${diagnostic.reason ? ` / ${diagnostic.reason}` : ""}`,
  ];
  if (diagnostic.affected_page_numbers.length) {
    lines.push(
      `受影响页：第 ${diagnostic.affected_page_numbers.join("、")} 页，共 ${diagnostic.fatal_count} 个阻断问题`
        + (diagnostic.details_truncated ? "（明细已截断，列表可能不完整）" : ""),
    );
  } else if (diagnostic.details_truncated) {
    lines.push("验证明细已截断，受影响页列表可能不完整");
  }
  return lines;
}
