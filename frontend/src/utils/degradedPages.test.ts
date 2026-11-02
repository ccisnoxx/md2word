import { describe, expect, it } from "vitest";

import { degradedPageLines, readDegradedPages, readSourcePageCounts, sourcePageCountLine } from "@/utils/degradedPages";

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

describe("源 PDF 页面统计", () => {
  const counts = {
    source_page_count: 37, converted_page_count: 33, degraded_page_count: 3, filtered_page_count: 1,
    page_count_basis: "mineru_layout",
  };

  it("完整依据显示总页数，过滤页非零才显示", () => {
    const read = readSourcePageCounts({ checks_v1: { document_base: { page_counts: counts } } });
    expect(sourcePageCountLine(read)).toBe("源 PDF 共 37 页：已转换 33 页，整页降级 3 页，已过滤 1 页");
  });

  it("仅有内容块依据时显示下限", () => {
    const read = readSourcePageCounts({ checks_v1: { document_base: { page_counts: {
      ...counts, filtered_page_count: 0, page_count_basis: "content_blocks",
    } } } });
    expect(sourcePageCountLine(read)).toBe("源 PDF 至少 37 页：已转换 33 页，整页降级 3 页");
  });

  it("旧任务或字段不完整时不展示", () => {
    expect(readSourcePageCounts({})).toBeNull();
    expect(readSourcePageCounts({ checks_v1: { document_base: { page_counts: { source_page_count: 3 } } } })).toBeNull();
    expect(sourcePageCountLine(null)).toBe("");
  });
});
