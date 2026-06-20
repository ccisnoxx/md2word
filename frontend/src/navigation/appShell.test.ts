import { describe, expect, it } from "vitest";
import type { RouteLocationNormalizedLoaded } from "vue-router";

import { getAppNavigationGroups, getAppRouteContext, getDefaultProtectedRoute, type AppAccessContext } from "@/navigation/appShell";

const operatorAccess: AppAccessContext = {
  role: "operator",
  roles: ["operator"],
  permissions: [
    "document_jobs:read",
    "document_jobs:create",
    "translation_qa:read",
    "translation_qa:write",
    "term_proposals:read",
    "term_proposals:create",
  ],
};

const adminAccess: AppAccessContext = {
  role: "admin",
  roles: ["admin"],
  permissions: [
    ...operatorAccess.permissions,
    "settings:read",
    "system:read",
    "ops:read",
    "audit:read",
    "files:retention",
    "term_proposals:review",
  ],
};

function routeFixture(
  name: string,
  params: Record<string, string> = {},
  query: Record<string, string> = {},
): RouteLocationNormalizedLoaded {
  return {
    name,
    params,
    query,
  } as unknown as RouteLocationNormalizedLoaded;
}

describe("app shell navigation", () => {
  it("filters workflow groups with the same all-permission semantics as route guards", () => {
    const operatorGroups = getAppNavigationGroups(operatorAccess);
    const operatorItemIds = operatorGroups.flatMap((group) => group.items.map((item) => item.id));

    expect(operatorGroups.map((group) => group.id)).toEqual(["processing", "quality"]);
    expect(operatorItemIds).toEqual(["cockpit", "jobs", "incidents", "job-create", "translation-qa", "term-proposals"]);
    expect(operatorItemIds).not.toContain("settings");
    expect(operatorItemIds).not.toContain("system-status");

    const adminItemIds = getAppNavigationGroups(adminAccess).flatMap((group) => group.items.map((item) => item.id));
    expect(adminItemIds).toContain("templates");
    expect(adminItemIds).toContain("ops-dashboard");
    expect(adminItemIds).toContain("file-retention");
  });

  it("shows the cockpit for any underlying source permission and keeps it first", () => {
    const qaOnlyGroups = getAppNavigationGroups({
      role: "operator",
      roles: ["operator"],
      permissions: ["translation_qa:read"],
    });
    const qaOnlyItemIds = qaOnlyGroups.flatMap((group) => group.items.map((item) => item.id));
    expect(qaOnlyItemIds[0]).toBe("cockpit");
    expect(qaOnlyItemIds).toContain("translation-qa");
    expect(qaOnlyItemIds).not.toContain("jobs");

    const settingsOnlyGroups = getAppNavigationGroups({
      role: "operator",
      roles: ["operator"],
      permissions: ["settings:read"],
    });
    expect(settingsOnlyGroups.flatMap((group) => group.items.map((item) => item.id))).not.toContain("cockpit");
  });

  it("resolves default protected landing with a cockpit-first fallback", () => {
    expect(getDefaultProtectedRoute(operatorAccess)).toBe("/cockpit");
    expect(
      getDefaultProtectedRoute({
        role: "operator",
        roles: ["operator"],
        permissions: ["settings:read"],
      }),
    ).toBe("/settings/term-rule-sets");
    expect(getDefaultProtectedRoute({ role: "guest", roles: ["guest"], permissions: [] })).toBe("/forbidden");
  });

  it("maps cockpit routes to the processing navigation context", () => {
    const context = getAppRouteContext(routeFixture("cockpit"), operatorAccess);
    expect(context.groupId).toBe("processing");
    expect(context.itemId).toBe("cockpit");
    expect(context.pageLabel).toBe("今日工作");
    expect(context.breadcrumbs.map((item) => item.label)).toEqual(["今日工作"]);
  });

  it("maps detail routes back to their owned sidebar item", () => {
    const detailContext = getAppRouteContext(routeFixture("job-detail", { jobId: "docjob_1" }), operatorAccess);
    expect(detailContext.groupId).toBe("processing");
    expect(detailContext.itemId).toBe("jobs");
    expect(detailContext.pageLabel).toBe("任务详情");
    expect(detailContext.breadcrumbs.map((item) => item.label)).toEqual(["任务工作台", "任务详情", "docjob_1"]);
  });

  it("uses translation QA ownership when the QA detail route returns to the QA queue", () => {
    const qaContext = getAppRouteContext(
      routeFixture("job-translation-qa", { jobId: "docjob_qa" }, { from: "translation-qa" }),
      operatorAccess,
    );
    expect(qaContext.groupId).toBe("quality");
    expect(qaContext.itemId).toBe("translation-qa");
    expect(qaContext.breadcrumbs[0]).toMatchObject({ label: "翻译 QA" });

    const jobsContext = getAppRouteContext(routeFixture("job-translation-qa", { jobId: "docjob_qa" }), operatorAccess);
    expect(jobsContext.groupId).toBe("processing");
    expect(jobsContext.itemId).toBe("jobs");
  });

  it("uses review terminology labels only when the permission is present", () => {
    expect(getAppRouteContext(routeFixture("term-proposals"), operatorAccess).breadcrumbs[0]?.label).toBe("术语建议");
    expect(getAppRouteContext(routeFixture("term-proposals"), adminAccess).breadcrumbs[0]?.label).toBe("提案审核");
  });
});
