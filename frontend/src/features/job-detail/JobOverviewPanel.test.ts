import { renderToString } from "@vue/server-renderer";
import ElementPlus, { ID_INJECTION_KEY } from "element-plus";
import { describe, expect, it } from "vitest";
import { createSSRApp, h } from "vue";

import type { DocumentJobFailureDiagnostic, DocumentJobResponse } from "@/api/types";
import JobOverviewPanel from "./JobOverviewPanel.vue";

function diagnostic(overrides: Partial<DocumentJobFailureDiagnostic> = {}): DocumentJobFailureDiagnostic {
  return {
    source: "render_operation", stage: "rendering", scope: "page", page_number: 1,
    source_type: null, json_pointer: null, reason_code: "ValueError", reason: null,
    affected_page_numbers: [1], fatal_count: 1, warning_count: 0, details_truncated: false,
    operation_kind: "block", block_ids: ["block_0001"], ...overrides,
  };
}

async function renderOverview(overrides: Partial<DocumentJobResponse> = {}): Promise<string> {
  const job = {
    id: "job-failed", status: "failed", stage: "failed", failed_stage: "rendering", mode: "direct_pdf_to_word",
    progress: 60, retry_count: 0, error_code: "render_failed", error_message: null,
    document_language: "auto", source_file_id: "pdf-source", request_snapshot: {}, available_actions: {},
    ...overrides,
  } as DocumentJobResponse;
  const app = createSSRApp({ render: () => h(JobOverviewPanel, {
    job, sourceFilename: "样例.pdf", translationQaReviewText: "", boundTemplateLabel: "默认模板",
    boundTermRuleSetLabel: "默认规则", boundTranslationTermSetLabel: "", boundTranslationProfileLabel: "",
    runningNotice: "", runningNoticeType: "info", downloadHint: "",
  }) });
  app.use(ElementPlus);
  app.provide(ID_INJECTION_KEY, { prefix: 0, current: 0 });
  return renderToString(app);
}

describe("任务概览真实组件渲染", () => {
  it.each([
    ["image_pair", "ValueError", "并排图片渲染", "具体原因尚未识别"],
    ["logical_table", "table_render_geometry", "表格渲染", "表格行列或合并单元格的几何结构无效"],
    ["block", "TypeError", "内容块渲染", "具体原因尚未识别"],
  ])("%s 失败显示中文阶段、原因和投影中的源 PDF 第 1 页", async (operation_kind, reason_code, operation, reason) => {
    const html = await renderOverview({ failure_diagnostic: diagnostic({ operation_kind, reason_code }) });
    expect(html).toContain('role="alert"');
    expect(html).toContain("任务处理失败");
    expect(html).toContain("失败阶段：生成 Word");
    expect(html).toContain(operation);
    expect(html).toContain(reason);
    expect(html).toContain("首个失败位置：源 PDF 第 1 页");
    expect(html).not.toContain("源 PDF 第 2 页");
    expect(html).not.toContain("block_0001");
  });

  it.each([null, undefined])("旧响应诊断为 %s 时明确未记录页码", async (failure_diagnostic) => {
    const html = await renderOverview({ failure_diagnostic, error_message: "Worker 执行发生未预期异常。" });
    expect(html).toContain("具体原因尚未识别");
    expect(html).toContain("未记录失败页码");
    expect(html).toContain("Worker 执行发生未预期异常。");
    expect(html).not.toContain("文档范围错误");
  });

  it("文档范围失败保留无法定位单页及截断语义", async () => {
    const html = await renderOverview({ failure_diagnostic: diagnostic({
      scope: "document", page_number: null, affected_page_numbers: [], details_truncated: true,
    }) });
    expect(html).toContain("文档范围错误，无法定位单页");
    expect(html).toContain("受影响页列表可能不完整");
    expect(html).not.toContain("源 PDF 第 1 页");
  });

  it.each(["running", "succeeded"] as const)("%s 任务不显示旧失败证据", async (status) => {
    const html = await renderOverview({ status, failure_diagnostic: diagnostic() });
    expect(html).not.toContain("任务处理失败");
    expect(html).not.toContain("失败阶段：");
    expect(html).not.toContain("首个失败位置");
  });
});
