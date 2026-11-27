// frontend/src/navigation/appShell.test.ts: 验证导航权限过滤和路由归属。
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
    "settings:write",
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
    expect(operatorItemIds).toEqual(["cockpit", "jobs", "incidents", "job-create", "translation-qa", "term-proposals", "term-rules"]);
    expect(operatorItemIds).not.toContain("settings");
    expect(operatorItemIds).not.toContain("system-status");

    const adminItemIds = getAppNavigationGroups(adminAccess).flatMap((group) => group.items.map((item) => item.id));
    expect(adminItemIds).toContain("templates");
    expect(adminItemIds).toContain("ops-dashboard");
    expect(adminItemIds).toContain("acceptance-center");
    expect(adminItemIds).toContain("file-retention");
    expect(adminItemIds).toContain("mineru-config");
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
    ).toBe("/settings/translation-term-sets");
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

  it("maps acceptance center into the system operations navigation context", () => {
    const context = getAppRouteContext(routeFixture("system-status-acceptance"), adminAccess);
    expect(context.groupId).toBe("system");
    expect(context.itemId).toBe("acceptance-center");
    expect(context.breadcrumbs.map((item) => item.label)).toEqual(["系统状态", "验收中心"]);
  });

  it("maps MinerU config into the configuration navigation context", () => {
    const context = getAppRouteContext(routeFixture("settings-mineru"), adminAccess);
    expect(context.groupId).toBe("configuration");
    expect(context.itemId).toBe("mineru-config");
    expect(context.breadcrumbs.map((item) => item.label)).toEqual(["配置中心", "MinerU 配置"]);
  });

  it("converges template and page-style sidebar entries, renames symbol rules, and overlays nav badges", () => {
    const adminGroups = getAppNavigationGroups(adminAccess, {
      incidents: { badge: "5", tone: "danger" },
      "translation-qa": { badge: "12", tone: "warning" },
    });
    const adminItems = adminGroups.flatMap((group) => group.items);

    expect(adminItems.find((item) => item.id === "term-rules")?.label).toBe("符号与排版规则");
    expect(adminItems.find((item) => item.id === "templates")?.label).toBe("模板与样式");
    expect(adminItems.find((item) => item.id === "word-page-styles")).toBeUndefined();
    expect(adminItems.find((item) => item.id === "incidents")).toMatchObject({ badge: "5", tone: "danger" });
    expect(adminItems.find((item) => item.id === "translation-qa")).toMatchObject({ badge: "12", tone: "warning" });

    // 页面样式旧路由继续兼容，并正确高亮合并后的「模板与样式」侧栏项。
    const styleContext = getAppRouteContext(routeFixture("settings-word-page-style-detail", { templateId: "default" }), adminAccess);
    expect(styleContext.groupId).toBe("configuration");
    expect(styleContext.itemId).toBe("templates");
    expect(styleContext.breadcrumbs.map((item) => item.label)).toEqual(["配置中心", "Word 页面样式配置", "default"]);

    const ruleContext = getAppRouteContext(routeFixture("settings-term-rules"), adminAccess);
    expect(ruleContext.pageLabel).toBe("符号与排版规则");
    expect(ruleContext.breadcrumbs.map((item) => item.label)).toEqual(["质量治理", "符号与排版规则", "当前生效规则"]);

    const reviewContext = getAppRouteContext(routeFixture("job-review", { jobId: "docjob_rev_1" }), operatorAccess);
    expect(reviewContext.groupId).toBe("processing");
    expect(reviewContext.itemId).toBe("jobs");
    expect(reviewContext.pageLabel).toBe("文档复核工作台");
    expect(reviewContext.breadcrumbs.map((item) => item.label)).toEqual(["任务工作台", "任务详情", "文档复核"]);
  });
});
