import { describe, expect, it } from "vitest";

import type { DocumentJobFailureDiagnostic } from "@/api/types";
import { failureDiagnosticLines, jobFailureSummaryLines } from "@/utils/failureDiagnostic";

function buildDiagnostic(overrides: Partial<DocumentJobFailureDiagnostic> = {}): DocumentJobFailureDiagnostic {
  return {
    source: "mineru_validation", stage: "ir_converting", scope: "page", page_number: 13,
    source_type: "image", json_pointer: "/content_list/148", reason_code: "invalid_image_asset",
    reason: "unreadable_or_unsupported_image", affected_page_numbers: [13, 15], fatal_count: 2,
    warning_count: 0, details_truncated: false, ...overrides,
  };
}

const failedJob = {
  status: "failed", stage: "failed", failed_stage: "rendering", error_code: "render_failed", error_message: null,
} as const;

describe("失败诊断共享文案", () => {
  it("已知图片原因使用中文，并保留技术码、首个失败与多页信息", () => {
    expect(failureDiagnosticLines(buildDiagnostic())).toEqual([
      "原因：图片资源无效；图片无法读取或格式不受支持",
      "首个失败位置：源 PDF 第 13 页",
      "受影响源页：源 PDF 第 13、15 页，共 2 个阻断问题",
      "诊断原因码：invalid_image_asset / unreadable_or_unsupported_image",
      "技术定位：image，/content_list/148",
    ]);
  });

  it("图片引用无效时不推断成图片损坏或格式问题", () => {
    expect(failureDiagnosticLines(buildDiagnostic({ reason: "invalid" }))[0]).toBe("原因：图片资源无效");
  });

  it("文档范围失败只说明无法定位单页", () => {
    const lines = failureDiagnosticLines(buildDiagnostic({
      scope: "document", page_number: null, source_type: null, json_pointer: null,
      reason_code: "mineru_package_limit_exceeded", reason: "entry_count", affected_page_numbers: [],
    }));
    expect(lines).toContain("首个失败位置：文档范围错误，无法定位单页");
    expect(lines[0]).toBe("原因：解析结果包超出处理限制；压缩包文件数量超出限制");
    expect(lines.join()).not.toContain("全部页面");
  });

  it("明细截断时提示列表可能不完整，无页列表时仍保留提示", () => {
    expect(failureDiagnosticLines(buildDiagnostic({ details_truncated: true })).join()).toContain("明细已截断，列表可能不完整");
    expect(failureDiagnosticLines(buildDiagnostic({ affected_page_numbers: [], details_truncated: true })))
      .toContain("验证明细已截断，受影响页列表可能不完整");
  });

  it("表格几何问题说明已知原因及操作，块信息留在技术明细", () => {
    const lines = failureDiagnosticLines(buildDiagnostic({
      source: "render_operation", stage: "rendering", page_number: 2, source_type: null, json_pointer: null,
      reason_code: "table_render_geometry", reason: null, affected_page_numbers: [2], fatal_count: 1,
      block_ids: ["block_0005"], operation_kind: "logical_table",
    }));
    expect(lines[0]).toBe("原因：表格渲染；表格行列或合并单元格的几何结构无效");
    expect(lines).toContain("技术定位：块 block_0005，操作 logical_table");
  });

  it.each([
    ["table_placeholder_geometry_invalid", "表格占位区域无效"],
    ["table_placeholder_crop_failed", "表格占位图裁剪失败"],
    ["table_placeholder_source_unavailable", "表格占位所需的源文件不可用"],
    ["table_placeholder_integrity_failed", "表格占位完整性校验失败"],
  ])("表格占位 %s 复用摘要并在详细诊断展示真实片段位置", (reason_code, reason) => {
    const diagnostic = buildDiagnostic({
      source: "table_placeholder", stage: "ir_converting", page_number: 2, affected_page_numbers: [2],
      reason_code, reason: null, source_type: null, json_pointer: null, fatal_count: 1,
      block_ids: ["block_0001"], operation_kind: "table_placeholder",
    });
    const lines = failureDiagnosticLines(diagnostic);
    expect(lines[0]).toBe(`原因：${reason}`);
    expect(lines).toContain("首个失败位置：源 PDF 第 2 页");
    expect(lines).toContain("技术定位：块 block_0001，操作 table_placeholder");
    const job = { ...failedJob, failed_stage: "ir_converting" as const, error_code: "document_ir_failed", failure_diagnostic: diagnostic };
    expect(jobFailureSummaryLines(job)).toContain(`原因：${reason}`);
    expect(jobFailureSummaryLines(job).join()).not.toContain("block_0001");
    expect(jobFailureSummaryLines(job, diagnostic, true)).toContain("技术定位：块 block_0001，操作 table_placeholder");
    expect(failureDiagnosticLines({ ...diagnostic, scope: "document", page_number: null, affected_page_numbers: [] }))
      .toContain("首个失败位置：文档范围错误，无法定位单页");
  });

  it("泛型异常不伪造根因，未知细分原因只保留机器码", () => {
    const lines = failureDiagnosticLines(buildDiagnostic({
      source: "render_operation", reason_code: "ValueError", reason: "future_reason", operation_kind: "block",
    }));
    expect(lines[0]).toBe("原因：内容块渲染；值校验异常（ValueError）；具体原因尚未识别，现有诊断信息不足");
    expect(lines).toContain("诊断原因码：ValueError / future_reason");
  });

  it("未知原因和操作不虚构中文解释，技术码保留", () => {
    const lines = failureDiagnosticLines(buildDiagnostic({
      source: "render_operation", reason_code: "future_error", reason: null, operation_kind: "future_operation",
    }));
    expect(lines[0]).toBe("原因：诊断码 future_error；具体原因尚未识别，现有诊断信息不足");
    expect(lines).toContain("诊断原因码：future_error");
    expect(lines).toContain("技术定位：操作 future_operation");
  });

  it("复用现有质量标记的中文说明", () => {
    expect(failureDiagnosticLines(buildDiagnostic({ reason_code: "missing_image_asset", reason: null }))[0])
      .toBe("原因：图片资产缺失");
  });

  it("区分源 PDF 精确总页数和内容块统计下限", () => {
    expect(failureDiagnosticLines(buildDiagnostic({ source_page_count: 20, page_count_basis: "mineru_layout" })))
      .toContain("源 PDF 共 20 页，本次未生成结果");
    expect(failureDiagnosticLines(buildDiagnostic({ source_page_count: 15, page_count_basis: "content_blocks" })))
      .toContain("源 PDF 至少 15 页，本次未生成结果");
  });

  it.each([null, undefined])("缺失诊断 %s 不当作文档级错误", (diagnostic) => {
    expect(failureDiagnosticLines(diagnostic)).toEqual(["失败位置：未记录失败页码"]);
    const lines = jobFailureSummaryLines({ ...failedJob, error_message: "Worker 执行发生未预期异常。" }, diagnostic, true);
    expect(lines).toContain("失败阶段：生成 Word");
    expect(lines).toContain("原因：Word 生成或质量检查失败；具体原因尚未识别，现有诊断信息不足");
    expect(lines).toContain("任务消息：Worker 执行发生未预期异常。");
    expect(lines).toContain("任务错误码：render_failed");
    expect(lines.join()).not.toContain("文档范围");
  });

  it("概览与详细诊断共享解释，后者额外保留技术信息", () => {
    const job = { ...failedJob, failure_diagnostic: buildDiagnostic() };
    const summary = jobFailureSummaryLines(job);
    expect(jobFailureSummaryLines(job, job.failure_diagnostic, true)).toEqual(expect.arrayContaining(summary));
    expect(summary.join()).not.toContain("invalid_image_asset");
    expect(summary.join()).not.toContain("/content_list/148");
  });

  it.each(["running", "succeeded"] as const)("%s 任务即使带旧诊断也没有失败摘要", (status) => {
    expect(jobFailureSummaryLines({ ...failedJob, status, failure_diagnostic: buildDiagnostic() })).toEqual([]);
  });
});
