import { describe, expect, it } from "vitest";

import {
  buildIncidentRouteQuery,
  isSameIncidentFilterRouteQuery,
  isSameIncidentRouteQuery,
  parseIncidentRouteQuery,
  type IncidentFilters,
} from "./incidentQuery";

describe("异常队列 URL query 映射", () => {
  it("筛选与抽屉任务可往返，空值不写入 query", () => {
    const filters: IncidentFilters = {
      status: "failed",
      stage: "",
      failureType: "artifact_missing",
      retryable: "true",
      retryCount: "",
      stalledMinutes: 30,
      q: " retry ",
      sort: "priority",
    };
    const query = buildIncidentRouteQuery(filters, 2, "docjob_a");
    expect(query).toEqual({
      page: "2",
      sort: "priority",
      status: "failed",
      failure_type: "artifact_missing",
      retryable: "true",
      stalled_minutes: "30",
      q: "retry",
      incident_job_id: "docjob_a",
    });
    expect(parseIncidentRouteQuery(query)).toEqual({ ...filters, q: "retry", page: 2 });
    expect(isSameIncidentRouteQuery(query, buildIncidentRouteQuery(filters, 2, null))).toBe(false);
  });

  it("只有 incident_job_id 变化时视为同一筛选，不触发队列重载", () => {
    expect(isSameIncidentFilterRouteQuery({ page: "1", sort: "priority" }, { page: "1", sort: "priority", incident_job_id: "x" })).toBe(true);
    expect(isSameIncidentFilterRouteQuery({ page: "1" }, { page: "2" })).toBe(false);
  });

  it("非法值回落默认：非正数停滞分钟与页码、未知重试性", () => {
    expect(parseIncidentRouteQuery({ stalled_minutes: "0", page: "abc", retryable: "maybe", sort: "x" })).toMatchObject({
      stalledMinutes: null,
      page: 1,
      retryable: "",
      sort: "priority",
    });
  });
});
