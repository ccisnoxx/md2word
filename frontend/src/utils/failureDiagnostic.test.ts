import { describe, expect, it } from "vitest";

import type { DocumentJobFailureDiagnostic } from "@/api/types";
import { failureDiagnosticLines } from "@/utils/failureDiagnostic";

function buildDiagnostic(overrides: Partial<DocumentJobFailureDiagnostic> = {}): DocumentJobFailureDiagnostic {
  return {
    source: "mineru_validation",
    stage: "ir_converting",
    scope: "page",
    page_number: 13,
    source_type: "image",
    json_pointer: "/content_list/148",
    reason_code: "invalid_image_asset",
    reason: "unreadable_or_unsupported_image",
    affected_page_numbers: [13, 15],
    fatal_count: 2,
    warning_count: 0,
    details_truncated: false,
    ...overrides,
  };
}

describe("failureDiagnosticLines", () => {
  it("页级失败展示页码、原因和受影响页", () => {
    expect(failureDiagnosticLines(buildDiagnostic())).toEqual([
      "首个失败位置：第 13 页（image，/content_list/148）",
      "原因：invalid_image_asset / unreadable_or_unsupported_image",
      "受影响页：第 13、15 页，共 2 个阻断问题",
    ]);
  });

  it("文档级失败不推测页码", () => {
    expect(failureDiagnosticLines(buildDiagnostic({
      scope: "document",
      page_number: null,
      source_type: null,
      json_pointer: null,
      reason_code: "mineru_package_limit_exceeded",
      reason: null,
      affected_page_numbers: [],
    }))).toEqual([
      "首个失败位置：文档级问题，无法定位到单页",
      "原因：mineru_package_limit_exceeded",
    ]);
  });

  it("明细截断时提示列表可能不完整", () => {
    expect(failureDiagnosticLines(buildDiagnostic({ details_truncated: true }))[2]).toContain("明细已截断");
    expect(failureDiagnosticLines(buildDiagnostic({ affected_page_numbers: [], details_truncated: true }))[2])
      .toBe("验证明细已截断，受影响页列表可能不完整");
  });

  it("渲染来源显示块与操作类型", () => {
    expect(failureDiagnosticLines(buildDiagnostic({
      source: "render_operation",
      stage: "rendering",
      page_number: 2,
      source_type: null,
      json_pointer: null,
      reason_code: "table_render_geometry",
      reason: null,
      affected_page_numbers: [2],
      fatal_count: 1,
      block_ids: ["block_0005"],
      operation_kind: "logical_table",
    }))).toEqual([
      "首个失败位置：第 2 页（块 block_0005，操作 logical_table）",
      "原因：table_render_geometry",
      "受影响页：第 2 页，共 1 个阻断问题",
    ]);
    expect(failureDiagnosticLines(buildDiagnostic({
      source: "render_operation", scope: "document", page_number: null, reason_code: "ValueError", reason: null,
      affected_page_numbers: [], block_ids: [], operation_kind: "decoration",
    }))[0]).toBe("首个失败位置：文档级问题，无法定位到单页（操作 decoration）");
  });

  it("无诊断时不输出", () => {
    expect(failureDiagnosticLines(null)).toEqual([]);
    expect(failureDiagnosticLines(undefined)).toEqual([]);
  });
});
