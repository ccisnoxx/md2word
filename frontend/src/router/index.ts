// 定义内部门户按需加载的页面路由与认证守卫。
import { ElMessage } from "element-plus";
import { createRouter, createWebHistory, type RouteLocationNormalized } from "vue-router";

import { setUnauthorizedHandler } from "@/api/client";
import AppLayout from "@/layouts/AppLayout.vue";
import { getDefaultProtectedRoute, type AppAccessContext } from "@/navigation/appShell";
import { pinia } from "@/stores";
import { useAuthStore } from "@/stores/auth";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: "/login",
      name: "login",
      component: () => import("@/pages/LoginPage.vue"),
      meta: { public: true },
    },
    {
      path: "/",
      component: AppLayout,
      meta: { requiresAuth: true },
      children: [
        { path: "", name: "protected-root", component: () => import("@/pages/OperationsCockpitPage.vue") },
        { path: "cockpit", name: "cockpit", component: () => import("@/pages/OperationsCockpitPage.vue") },
        { path: "forbidden", name: "forbidden", component: () => import("@/pages/ForbiddenPage.vue") },
        { path: "jobs", name: "jobs", component: () => import("@/pages/JobsPage.vue"), meta: { permissions: ["document_jobs:read"] } },
        { path: "incidents", name: "incidents", component: () => import("@/pages/IncidentTriagePage.vue"), meta: { permissions: ["document_jobs:read"] } },
        { path: "jobs/new", name: "job-create", component: () => import("@/pages/JobCreatePage.vue"), meta: { permissions: ["document_jobs:create"] } },
        { path: "jobs/:jobId", name: "job-detail", component: () => import("@/pages/JobDetailPage.vue"), props: true, meta: { permissions: ["document_jobs:read"] } },
        {
          path: "jobs/:jobId/translation-qa",
          name: "job-translation-qa",
          component: () => import("@/pages/TranslationResultQaPage.vue"),
          props: true,
          meta: { permissions: ["translation_qa:read"] },
        },
        { path: "translation-qa", name: "translation-qa", component: () => import("@/pages/TranslationQaQueuePage.vue"), meta: { permissions: ["translation_qa:read"] } },
        { path: "settings", name: "settings", component: () => import("@/pages/SettingsHomePage.vue"), meta: { permissions: ["settings:read"] } },
        { path: "settings/templates", name: "settings-templates", component: () => import("@/pages/TemplateListPage.vue"), meta: { roles: ["admin"], permissions: ["settings:read"] } },
        {
          path: "settings/word-page-styles",
          name: "settings-word-page-styles",
          component: () => import("@/pages/WordPageStyleListPage.vue"),
          meta: { roles: ["admin"], permissions: ["settings:read"] },
        },
        {
          path: "settings/word-page-styles/:templateId",
          name: "settings-word-page-style-detail",
          component: () => import("@/pages/WordPageStyleDetailPage.vue"),
          props: true,
          meta: { roles: ["admin"], permissions: ["settings:read"] },
        },
        {
          path: "settings/term-rule-sets",
          name: "settings-term-rule-sets",
          component: () => import("@/pages/TermRuleSetPage.vue"),
          meta: { permissions: ["settings:read"] },
        },
        {
          path: "settings/terminology-releases",
          name: "settings-terminology-releases",
          component: () => import("@/pages/TerminologyReleasesPage.vue"),
          meta: { permissions: ["settings:read"] },
        },
        {
          path: "settings/term-rules",
          name: "settings-term-rules",
          component: () => import("@/pages/TermRuleWorkbenchPage.vue"),
          meta: { permissions: ["term_proposals:read"] },
        },
        {
          path: "settings/translation-profiles",
          name: "settings-translation-profiles",
          component: () => import("@/pages/TranslationProfilesPage.vue"),
          meta: { permissions: ["settings:read"] },
        },
        {
          path: "settings/ai-provider",
          name: "settings-ai-provider",
          component: () => import("@/pages/AiProviderConfigPage.vue"),
          meta: { roles: ["admin"], permissions: ["settings:write"] },
        },
        {
          path: "settings/mineru",
          name: "settings-mineru",
          component: () => import("@/pages/MinerUConfigPage.vue"),
          meta: { roles: ["admin"], permissions: ["settings:write"] },
        },
        {
          path: "settings/translation-term-sets",
          name: "settings-translation-term-sets",
          component: () => import("@/pages/TranslationTermSetPage.vue"),
          meta: { permissions: ["settings:read"] },
        },
        {
          path: "settings/templates/:templateId",
          name: "settings-template-detail",
          component: () => import("@/pages/TemplateDetailPage.vue"),
          props: true,
          meta: { roles: ["admin"], permissions: ["settings:read"] },
        },
        {
          path: "term-rule-reviews",
          name: "term-rule-reviews",
          component: () => import("@/pages/TermRuleReviewFlowPage.vue"),
          meta: { permissions: ["term_proposals:read"] },
        },
        { path: "term-proposals", name: "term-proposals", component: () => import("@/pages/TermProposalsPage.vue"), meta: { permissions: ["term_proposals:read"] } },
        { path: "system-status", name: "system-status", component: () => import("@/pages/SystemStatusPage.vue"), meta: { permissions: ["system:read"] } },
        {
          path: "system-status/ops-dashboard",
          name: "system-status-ops-dashboard",
          component: () => import("@/pages/OpsDashboardPage.vue"),
          meta: { permissions: ["ops:read"] },
        },
        {
          path: "system-status/acceptance",
          name: "system-status-acceptance",
          component: () => import("@/pages/AcceptanceCenterPage.vue"),
          meta: { roles: ["admin"], permissions: ["ops:read"] },
        },
        {
          path: "system-status/audit-events",
          name: "system-status-audit-events",
          component: () => import("@/pages/AuditLogPage.vue"),
          meta: { permissions: ["audit:read"] },
        },
        {
          path: "system-status/users",
          name: "system-status-users",
          component: () => import("@/pages/UserManagementPage.vue"),
          meta: { roles: ["admin"], permissions: ["users:manage"] },
        },
        {
          path: "system-status/file-retention",
          name: "system-status-file-retention",
          component: () => import("@/pages/FileRetentionPage.vue"),
          meta: { permissions: ["files:retention"] },
        },
      ],
    },
    {
      path: "/:pathMatch(.*)*",
      redirect: "/cockpit",
    },
  ],
});

// 发布会原子切换静态目录，旧标签页按旧 hash 请求的页面 chunk 会 404；
// Vite 对页面模块及其依赖的加载失败统一派发该事件，并随后抛出同一个错误对象。
const chunkLoadErrors = new WeakSet<object>();
const CHUNK_RELOAD_AT_KEY = "md2word.frontend.chunk_reload_at";
// 窗口内再次失败说明不是旧版本问题（如网络中断），改为提示而不再刷新，避免循环。
const CHUNK_RELOAD_WINDOW_MS = 10_000;

if (typeof window !== "undefined") {
  window.addEventListener("vite:preloadError", (event) => {
    const payload: unknown = (event as Event & { payload?: unknown }).payload;
    if (typeof payload === "object" && payload !== null) {
      chunkLoadErrors.add(payload);
    }
  });
}

function reloadForStaleChunk(to: RouteLocationNormalized): boolean {
  const now = Date.now();
  const lastReloadAt = Number(window.sessionStorage.getItem(CHUNK_RELOAD_AT_KEY) ?? 0);
  if (now - lastReloadAt < CHUNK_RELOAD_WINDOW_MS) {
    return false;
  }
  window.sessionStorage.setItem(CHUNK_RELOAD_AT_KEY, String(now));
  window.location.assign(router.resolve(to.fullPath).href);
  return true;
}

// 首次深链接失败时尚无页面可展示错误，由全局消息保留可见反馈。
router.onError((error, to) => {
  if (typeof error === "object" && error !== null && chunkLoadErrors.has(error) && reloadForStaleChunk(to)) {
    return;
  }
  ElMessage.error({
    message: "页面加载失败，请检查网络后重新打开此页面。",
    duration: 0,
    showClose: true,
  });
  console.error("页面导航失败：", error);
});

function authAccess(auth: ReturnType<typeof useAuthStore>): AppAccessContext {
  return {
    role: auth.user?.role ?? null,
    roles: auth.user?.roles ?? [],
    permissions: auth.user?.permissions ?? [],
  };
}

function loginRedirect(
  to: RouteLocationNormalized,
  authReason?: string,
): { path: string; query: Record<string, string> } {
  const query: Record<string, string> = to.fullPath === "/login" ? {} : { redirect: to.fullPath };
  if (authReason) {
    query.auth = authReason;
  }
  return {
    path: "/login",
    query,
  };
}

function authFailureReason(caught: unknown): string {
  if (typeof caught === "object" && caught !== null && "code" in caught && caught.code === "token_expired") {
    return "token_expired";
  }
  return "invalid_token";
}

function routeMetaList(to: RouteLocationNormalized, key: "roles" | "permissions"): string[] {
  const values: string[] = [];
  for (const record of to.matched) {
    const rawValue = record.meta[key];
    if (Array.isArray(rawValue)) {
      values.push(...rawValue.filter((value): value is string => typeof value === "string"));
    }
  }
  return values;
}

function routeRoles(to: RouteLocationNormalized): string[] {
  return routeMetaList(to, "roles");
}

function routePermissions(to: RouteLocationNormalized): string[] {
  return routeMetaList(to, "permissions");
}

router.beforeEach(async (to) => {
  const auth = useAuthStore(pinia);
  const isPublic = Boolean(to.meta.public);

  if (to.path === "/login" && auth.token) {
    try {
      if (!auth.user) {
        await auth.loadCurrentUser();
      }
      return getDefaultProtectedRoute(authAccess(auth));
    } catch {
      auth.logout();
      return true;
    }
  }

  if (!isPublic && !auth.token) {
    return loginRedirect(to);
  }

  if (!isPublic && auth.token && !auth.user) {
    try {
      await auth.loadCurrentUser();
    } catch (caught) {
      auth.logout();
      return loginRedirect(to, authFailureReason(caught));
    }
  }

  if (to.name === "protected-root") {
    return getDefaultProtectedRoute(authAccess(auth));
  }

  const allowedRoles = routeRoles(to);
  if (allowedRoles.length > 0 && !allowedRoles.includes(auth.user?.role ?? "")) {
    return {
      path: "/forbidden",
      query: { from: to.fullPath, required: allowedRoles.join(",") },
    };
  }

  const requiredPermissions = routePermissions(to);
  if (requiredPermissions.length > 0 && !requiredPermissions.every((permission) => auth.hasPermission(permission))) {
    return {
      path: "/forbidden",
      query: { from: to.fullPath, required: requiredPermissions.join(",") },
    };
  }

  return true;
});

setUnauthorizedHandler((error) => {
  const auth = useAuthStore(pinia);
  auth.logout();
  if (router.currentRoute.value.path !== "/login") {
    void router.push(loginRedirect(router.currentRoute.value, authFailureReason(error)));
  }
});

export default router;
