import { describe, expect, it } from "vitest";

import { degradedPageLines, readDegradedPages } from "@/utils/degradedPages";

describe("readDegradedPages", () => {
  it("读取基础质量中的降级页并过滤不完整条目", () => {
    const summary = {
      checks_v1: {
        document_base: {
          degraded_pages: [
            { page_number: 2, trigger: "validation", reason_codes: ["invalid_table_html"] },
            { page_number: 0, trigger: "render", reason_codes: [] },
            { page_number: 5, trigger: "other", reason_codes: [] },
          ],
        },
      },
    };
    expect(readDegradedPages(summary)).toEqual([
      { page_number: 2, trigger: "validation", reason_codes: ["invalid_table_html"] },
    ]);
  });

  it("旧任务没有降级字段时返回空", () => {
    expect(readDegradedPages({})).toEqual([]);
    expect(readDegradedPages(undefined)).toEqual([]);
  });
});

describe("degradedPageLines", () => {
  it("按阶段与原因生成提示文案", () => {
    expect(degradedPageLines([
      { page_number: 2, trigger: "validation", reason_codes: ["invalid_table_html"] },
      { page_number: 3, trigger: "render", reason_codes: [] },
    ])).toEqual([
      "第 2 页：验证阶段降级，原因 invalid_table_html",
      "第 3 页：渲染阶段降级，原因 依赖页一并降级",
    ]);
  });
});
