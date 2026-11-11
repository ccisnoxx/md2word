import { describe, expect, it } from "vitest";

import { buildJobsRouteQuery, isSameJobsRouteQuery, parseJobsRouteQuery } from "./jobsListQuery";

describe("任务列表 URL query 映射", () => {
  it("完整筛选可往返：构造的 query 解析后得到相同筛选与页码", () => {
    const filters = {
      status: "failed" as const,
      statusGroup: "" as const,
      qaStatus: "blocked" as const,
      q: "  report  ",
      sort: "updated_at_asc" as const,
      includeArchived: true,
      createdRange: ["2026-06-01T00:00:00Z", "2026-06-02T00:00:00Z"] as [string, string],
    };
    const query = buildJobsRouteQuery(filters, 3);
    expect(query).toEqual({
      status: "failed",
      translation_qa_status: "blocked",
      q: "report",
      sort: "updated_at_asc",
      include_archived: "true",
      page: "3",
      created_from: "2026-06-01T00:00:00Z",
      created_to: "2026-06-02T00:00:00Z",
    });
    expect(parseJobsRouteQuery(query)).toEqual({ ...filters, q: "report", page: 3 });
    expect(isSameJobsRouteQuery(query, query)).toBe(true);
  });

  it("非法值回落默认；status 存在时忽略 status_group；只给一端日期不形成区间", () => {
    expect(parseJobsRouteQuery({
      status: "running",
      status_group: "active",
      translation_qa_status: "unknown",
      sort: "random",
      page: "-2",
      created_from: "2026-06-01T00:00:00Z",
    })).toEqual({
      status: "running",
      statusGroup: "",
      qaStatus: "",
      q: "",
      sort: "created_at_desc",
      page: 1,
      includeArchived: false,
      createdRange: null,
    });
    expect(parseJobsRouteQuery({ status_group: ["active", "x"] }).statusGroup).toBe("active");
  });

  it("缺省 query 与默认筛选的规范 query 视为不同，触发首次 replace 同步", () => {
    const defaults = parseJobsRouteQuery({});
    expect(isSameJobsRouteQuery({}, buildJobsRouteQuery(defaults, 1))).toBe(false);
  });
});
