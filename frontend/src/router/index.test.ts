import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { RouteComponent, Router } from "vue-router";

import { ElMessage } from "element-plus";
import { authApi } from "@/api/auth";
import { setUnauthorizedHandler } from "@/api/client";
import type { CurrentUserResponse } from "@/api/types";

vi.mock("vue-router", async (importOriginal) => {
  const actual = await importOriginal<typeof import("vue-router")>();
  return { ...actual, createWebHistory: actual.createMemoryHistory };
});
vi.mock("element-plus", () => ({ ElMessage: { error: vi.fn() } }));
vi.mock("@/api/auth", () => ({ authApi: { login: vi.fn(), me: vi.fn() } }));
vi.mock("@/api/client", () => ({ setUnauthorizedHandler: vi.fn() }));
vi.mock("@/layouts/AppLayout.vue", () => ({ default: { name: "AppLayout", render: () => null } }));

const pageNames = [
  "AcceptanceCenterPage", "AiProviderConfigPage", "AuditLogPage", "FileRetentionPage",
  "ForbiddenPage", "IncidentTriagePage", "JobCreatePage", "JobDetailPage", "JobsPage",
  "LoginPage", "MinerUConfigPage", "OpsDashboardPage", "OperationsCockpitPage",
  "SettingsHomePage", "SystemStatusPage", "TemplateDetailPage", "TemplateListPage",
  "TermRuleWorkbenchPage", "TermRuleReviewFlowPage", "TermRuleSetPage", "TermProposalsPage",
  "TerminologyReleasesPage", "TranslationProfilesPage", "TranslationQaQueuePage",
  "TranslationResultQaPage", "TranslationTermSetPage", "UserManagementPage",
  "WordPageStyleDetailPage", "WordPageStyleListPage",
];
const loadedPages: string[] = [];
let router: Router;
let auth: ReturnType<typeof import("@/stores/auth").useAuthStore>;

function user(role = "operator", permissions = ["document_jobs:read"]): CurrentUserResponse {
  return {
    id: "user_test", username: "test", role, roles: [role], permissions,
    tenant_id: "tenant_test", company_id: "company_test", display_name: null,
  };
}

function signIn(role = "operator", permissions = ["document_jobs:read"]): void {
  auth.token = "test_token";
  auth.user = user(role, permissions);
}

beforeEach(async () => {
  vi.resetModules();
  vi.clearAllMocks();
  loadedPages.length = 0;
  for (const name of pageNames) {
    vi.doMock(`@/pages/${name}.vue`, () => {
      loadedPages.push(name);
      return { default: { name, render: () => null } };
    });
  }
  router = (await import("@/router")).default;
  const { pinia } = await import("@/stores");
  const { useAuthStore } = await import("@/stores/auth");
  auth = useAuthStore(pinia);
});

afterEach(() => {
  router.options.history.destroy();
  vi.restoreAllMocks();
});

describe("按需加载的页面路由", () => {
  it("注册路由和进入登录页时不提前加载业务或管理页面", async () => {
    expect(loadedPages).toEqual([]);
    await router.push("/login");
    expect(loadedPages).toEqual(["LoginPage"]);
  });

  it("登录后按原 redirect 返回包含查询和锚点的深链接", async () => {
    const target = "/jobs/job_42?tab=events&filter=failed#details";
    await router.push(target);
    expect(router.currentRoute.value.path).toBe("/login");
    expect(router.currentRoute.value.query.redirect).toBe(target);
    expect(loadedPages).toEqual(["LoginPage"]);
    // LoginPage 在认证成功后将该原始 redirect 交给 router.push。
    const redirect = router.currentRoute.value.query.redirect as string;
    signIn();
    await router.push(redirect);
    expect(router.currentRoute.value.fullPath).toBe(target);
    expect(router.currentRoute.value.params).toEqual({ jobId: "job_42" });
    expect(router.currentRoute.value.query).toEqual({ tab: "events", filter: "failed" });
    expect(router.currentRoute.value.matched[router.currentRoute.value.matched.length - 1].props.default).toBe(true);
    expect(loadedPages).toEqual(["LoginPage", "JobDetailPage"]);
  });

  it.each([
    ["/jobs/job_42/translation-qa?from=translation-qa", "job-translation-qa", "TranslationResultQaPage", { jobId: "job_42" }],
    ["/settings/templates/template_42?version=2", "settings-template-detail", "TemplateDetailPage", { templateId: "template_42" }],
    ["/settings/word-page-styles/style_42?version=3", "settings-word-page-style-detail", "WordPageStyleDetailPage", { templateId: "style_42" }],
  ] as const)("首次深链接 %s 保留参数、查询和 props", async (target, name, page, params) => {
    auth.token = "restored_token";
    vi.mocked(authApi.me).mockResolvedValue(user("admin", ["translation_qa:read", "settings:read"]));
    await router.push(target);
    await router.isReady();
    expect(authApi.me).toHaveBeenCalledTimes(1);
    expect(router.currentRoute.value.fullPath).toBe(target);
    expect(router.currentRoute.value.name).toBe(name);
    expect(router.currentRoute.value.params).toEqual(params);
    expect(router.currentRoute.value.matched[router.currentRoute.value.matched.length - 1].props.default).toBe(true);
    expect(loadedPages).toEqual([page]);
  });

  it.each(["/", "/login", "/unknown/path"])("已认证访问 %s 保留默认入口", async (target) => {
    signIn();
    await router.push(target);
    expect(router.currentRoute.value.path).toBe("/cockpit");
    expect(loadedPages).toEqual(["OperationsCockpitPage"]);
  });

  it("权限不足时不加载目标页面", async () => {
    signIn();
    await router.push("/jobs/new?mode=direct");
    expect(router.currentRoute.value.path).toBe("/forbidden");
    expect(router.currentRoute.value.query).toEqual({
      from: "/jobs/new?mode=direct", required: "document_jobs:create",
    });
    expect(loadedPages).toEqual(["ForbiddenPage"]);
  });

  it("拥有权限但角色不符时仍不加载管理页面", async () => {
    signIn("operator", ["settings:read"]);
    await router.push("/settings/templates");
    expect(router.currentRoute.value.path).toBe("/forbidden");
    expect(router.currentRoute.value.query.required).toBe("admin");
    expect(loadedPages).toEqual(["ForbiddenPage"]);
  });

  it("管理角色仍须拥有对应权限", async () => {
    signIn("admin");
    await router.push("/settings/ai-provider");
    expect(router.currentRoute.value.path).toBe("/forbidden");
    expect(router.currentRoute.value.query.required).toBe("settings:write");
    expect(loadedPages).toEqual(["ForbiddenPage"]);
  });

  it("角色与权限均满足时才加载管理页面", async () => {
    signIn("admin", ["settings:write"]);
    await router.push("/settings/ai-provider");
    expect(router.currentRoute.value.name).toBe("settings-ai-provider");
    expect(loadedPages).toEqual(["AiProviderConfigPage"]);
  });

  it("恢复令牌失效时保留登录原因和原始深链接", async () => {
    auth.token = "expired_token";
    vi.mocked(authApi.me).mockRejectedValue({ code: "token_expired" });
    await router.push("/jobs/job_42?tab=events");
    expect(auth.token).toBeNull();
    expect(router.currentRoute.value.path).toBe("/login");
    expect(router.currentRoute.value.query).toEqual({
      redirect: "/jobs/job_42?tab=events", auth: "token_expired",
    });
    expect(loadedPages).toEqual(["LoginPage"]);
  });

  it("运行中收到未授权响应时清理认证并保留回跳地址", async () => {
    signIn();
    await router.push("/jobs/job_42?tab=events");
    const completed = new Promise<void>((resolve) => {
      const remove = router.afterEach(() => { remove(); resolve(); });
    });
    const handler = vi.mocked(setUnauthorizedHandler).mock.calls[0][0];
    handler?.({ code: "token_expired" } as Parameters<NonNullable<typeof handler>>[0]);
    await completed;
    expect(auth.token).toBeNull();
    expect(router.currentRoute.value.path).toBe("/login");
    expect(router.currentRoute.value.query).toEqual({
      redirect: "/jobs/job_42?tab=events", auth: "token_expired",
    });
  });

  it.each([false, true])("页面加载失败保留拒绝并允许手动再次导航（已有页面：%s）", async (hasPage) => {
    signIn();
    if (hasPage) await router.push("/cockpit");
    const previousRoute = router.currentRoute.value;
    const record = router.getRoutes().find((route) => route.name === "job-detail")!;
    const originalLoader = record.components!.default as () => Promise<RouteComponent>;
    const failure = new Error("测试：页面模块加载失败");
    const loader = vi.fn(originalLoader).mockRejectedValueOnce(failure);
    record.components!.default = loader;
    const log = vi.spyOn(console, "error").mockImplementation(() => {});
    const readyFailure = hasPage ? null : expect(router.isReady()).rejects.toBe(failure);
    await expect(router.push("/jobs/job_42?tab=events")).rejects.toBe(failure);
    if (readyFailure) await readyFailure;
    expect(ElMessage.error).toHaveBeenCalledExactlyOnceWith({
      message: "页面加载失败，请检查网络后重新打开此页面。",
      duration: 0,
      showClose: true,
    });
    expect(log).toHaveBeenCalledWith("页面导航失败：", failure);
    expect(router.currentRoute.value).toBe(previousRoute);
    expect(loader).toHaveBeenCalledTimes(1);
    await router.push("/jobs/job_42?tab=events");
    await router.isReady();
    expect(router.currentRoute.value.fullPath).toBe("/jobs/job_42?tab=events");
    expect(loader).toHaveBeenCalledTimes(2);
    expect(loadedPages).toContain("JobDetailPage");
    expect(ElMessage.error).toHaveBeenCalledTimes(1);
  });
});
