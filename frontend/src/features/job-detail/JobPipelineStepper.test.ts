import { renderToString } from "@vue/server-renderer";
import ElementPlus, { ID_INJECTION_KEY } from "element-plus";
import { describe, expect, it } from "vitest";
import { createSSRApp, h } from "vue";

import type { DocumentJobResponse } from "@/api/types";
import JobPipelineStepper from "./JobPipelineStepper.vue";

async function renderStepper(overrides: Partial<DocumentJobResponse> = {}): Promise<string> {
  const job = {
    id: "job-stepper",
    status: "running",
    stage: "rendering",
    failed_stage: null,
    mode: "direct_pdf_to_word",
    translation_mode: "direct",
    progress: 70,
    retry_count: 0,
    error_code: null,
    error_message: null,
    document_language: "auto",
    source_file_id: "pdf-source",
    request_snapshot: {},
    available_actions: {},
    ...overrides,
  } as DocumentJobResponse;
  const app = createSSRApp({ render: () => h(JobPipelineStepper, { job }) });
  app.use(ElementPlus);
  app.provide(ID_INJECTION_KEY, { prefix: 0, current: 0 });
  return renderToString(app);
}

describe("任务水平阶段进度条真实渲染", () => {
  it("direct 模式省略翻译与翻译校验节点，翻译模式展示完整 8 阶段", async () => {
    const directHtml = await renderStepper({ mode: "direct_pdf_to_word", translation_mode: "direct", stage: "rendering" });
    expect(directHtml).toContain("解析 PDF");
    expect(directHtml).toContain("生成 Word");
    expect(directHtml).toContain("检查文档质量");
    expect(directHtml).not.toContain("翻译中");
    expect(directHtml).not.toContain("校验翻译完整性");

    const translationHtml = await renderStepper({
      mode: "en2zh_pdf_to_word",
      translation_mode: "en2zh",
      stage: "translating",
    });
    expect(translationHtml).toContain("翻译中");
    expect(translationHtml).toContain("校验翻译完整性");
  });

  it("失败任务展示失败阶段、错误码和后端源 PDF 页码，缺失页码时不猜测", async () => {
    const withPageHtml = await renderStepper({
      status: "failed",
      stage: "failed",
      failed_stage: "quality_checking",
      error_code: "render_failed",
      failure_diagnostic: {
        source: "render_operation",
        stage: "quality_checking",
        scope: "page",
        page_number: 3,
        source_type: null,
        json_pointer: null,
        reason_code: "table_render_geometry",
        reason: null,
        affected_page_numbers: [3],
        fatal_count: 1,
        warning_count: 0,
        details_truncated: false,
        operation_kind: "logical_table",
        block_ids: ["block_0007"],
      },
    });
    expect(withPageHtml).toContain("task-disposition-fact");
    expect(withPageHtml).toContain("失败阶段");
    expect(withPageHtml).toContain("检查文档质量");
    expect(withPageHtml).toContain("render_failed");
    expect(withPageHtml).toContain("源 PDF 第 3 页");

    const withoutPageHtml = await renderStepper({
      status: "failed",
      stage: "failed",
      failed_stage: "parsing",
      error_code: "mineru_failed",
      failure_diagnostic: null,
    });
    expect(withoutPageHtml).toContain("解析 PDF");
    expect(withoutPageHtml).toContain("mineru_failed");
    expect(withoutPageHtml).not.toContain("源 PDF 第");
  });

  it("未知阶段名原文回显而不崩溃", async () => {
    const html = await renderStepper({
      status: "running",
      stage: "future_stage_preview" as DocumentJobResponse["stage"],
    });
    expect(html).toContain("当前阶段：future_stage_preview");
  });
});
