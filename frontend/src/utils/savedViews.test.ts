import { describe, expect, it } from "vitest";

import type { SavedViewResponse } from "@/api/types";
import {
  activeSavedViewId,
  hasMeaningfulSavedViewQuery,
  incidentsSavedViewStateToQuery,
  jobsSavedViewStateToQuery,
  personalSavedViewToStripItem,
  routeForSavedView,
  systemSavedViews,
  translationQaSavedViewStateToQuery,
} from "@/utils/savedViews";

function buildSavedView(overrides: Partial<SavedViewResponse> = {}): SavedViewResponse {
  return {
    view_id: "savedview_1",
    tenant_id: "tenant_default",
    company_id: "company_default",
    owner_user_id: "user_operator",
    page_key: "jobs",
    name: "失败任务",
    filters: { status: "failed" },
    sort: "updated_at_desc",
    is_default: false,
    position: 0,
    created_at: "2026-06-20T00:00:00Z",
    updated_at: "2026-06-20T00:00:00Z",
    ...overrides,
  };
}

describe("saved view helpers", () => {
  it("maps personal API rows to strip items and matches canonical active state", () => {
    const personal = personalSavedViewToStripItem(buildSavedView());
    const activeId = activeSavedViewId(
      { filters: { q: "", status: "failed" }, sort: "updated_at_desc" },
      [systemSavedViews.jobs[0], personal],
    );

    expect(personal).toMatchObject({
      id: "savedview_1",
      source: "personal",
      page_key: "jobs",
      name: "失败任务",
    });
    expect(activeId).toBe("savedview_1");
  });

  it("keeps system presets Chinese-first for operator-visible labels", () => {
    expect(systemSavedViews.jobs.map((view) => view.name)).toEqual(["处理中任务", "失败任务", "待 QA", "QA 阻塞"]);
    expect(systemSavedViews.translation_qa.map((view) => view.name)).toEqual(["待复核", "需修正", "阻塞", "已通过"]);
    expect(systemSavedViews.incidents.map((view) => view.name)).toEqual(["可重试异常", "停滞优先", "产物缺失", "多次重试"]);
  });

  it("treats only durable filter and sort query keys as meaningful", () => {
    expect(hasMeaningfulSavedViewQuery({ page: "3" }, "jobs")).toBe(false);
    expect(hasMeaningfulSavedViewQuery({ qa_job_id: "docjob_1" }, "translation_qa")).toBe(false);
    expect(hasMeaningfulSavedViewQuery({ incident_job_id: "docjob_1" }, "incidents")).toBe(false);
    expect(hasMeaningfulSavedViewQuery({ sort: "updated_at_desc" }, "jobs")).toBe(true);
    expect(hasMeaningfulSavedViewQuery({ status: "failed" }, "incidents")).toBe(true);
  });

  it("builds jobs query from saved state without persisting page or selection state", () => {
    expect(
      jobsSavedViewStateToQuery(
        {
          filters: {
            status_group: "active",
            q: "invoice",
            include_archived: true,
          },
          sort: "updated_at_asc",
        },
        4,
      ),
    ).toEqual({
      status_group: "active",
      q: "invoice",
      include_archived: "true",
      sort: "updated_at_asc",
      page: "4",
    });
  });

  it("preserves drawer ids only when applying queue and incident queries", () => {
    expect(
      translationQaSavedViewStateToQuery(
        { filters: { translation_qa_status: "blocked" }, sort: "updated_at_desc" },
        1,
        "docjob_qa",
      ),
    ).toMatchObject({
      translation_qa_status: "blocked",
      qa_job_id: "docjob_qa",
      page: "1",
    });
    expect(
      incidentsSavedViewStateToQuery(
        { filters: { retryable: true, stalled_minutes: 10 }, sort: "priority" },
        1,
        "docjob_incident",
      ),
    ).toMatchObject({
      retryable: "true",
      stalled_minutes: "10",
      incident_job_id: "docjob_incident",
      page: "1",
    });
  });

  it("builds saved-view routes from the shared workbench query helpers", () => {
    expect(routeForSavedView({ page_key: "jobs", filters: { status: "failed" }, sort: "updated_at_desc" })).toMatchObject({
      name: "jobs",
      query: { status: "failed", page: "1" },
    });
    expect(routeForSavedView({ page_key: "translation_qa", filters: { translation_qa_status: "blocked" }, sort: "updated_at_desc" })).toMatchObject({
      name: "translation-qa",
      query: { translation_qa_status: "blocked", page: "1" },
    });
  });
});
