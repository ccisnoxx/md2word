// File: frontend/src/router/index.ts
// Purpose: Define static internal portal/Admin routes and the auth guard.
import { createRouter, createWebHistory, type RouteLocationNormalized } from "vue-router";

import { setUnauthorizedHandler } from "@/api/client";
import AppLayout from "@/layouts/AppLayout.vue";
import AcceptanceCenterPage from "@/pages/AcceptanceCenterPage.vue";
import AuditLogPage from "@/pages/AuditLogPage.vue";
import FileRetentionPage from "@/pages/FileRetentionPage.vue";
import ForbiddenPage from "@/pages/ForbiddenPage.vue";
import IncidentTriagePage from "@/pages/IncidentTriagePage.vue";
import JobCreatePage from "@/pages/JobCreatePage.vue";
import JobDetailPage from "@/pages/JobDetailPage.vue";
import JobsPage from "@/pages/JobsPage.vue";
import LoginPage from "@/pages/LoginPage.vue";
import OpsDashboardPage from "@/pages/OpsDashboardPage.vue";
import OperationsCockpitPage from "@/pages/OperationsCockpitPage.vue";
import SettingsHomePage from "@/pages/SettingsHomePage.vue";
import SystemStatusPage from "@/pages/SystemStatusPage.vue";
import TemplateDetailPage from "@/pages/TemplateDetailPage.vue";
import TemplateListPage from "@/pages/TemplateListPage.vue";
import TermRuleWorkbenchPage from "@/pages/TermRuleWorkbenchPage.vue";
import TermRuleReviewFlowPage from "@/pages/TermRuleReviewFlowPage.vue";
import TermRuleSetPage from "@/pages/TermRuleSetPage.vue";
import TermProposalsPage from "@/pages/TermProposalsPage.vue";
import TerminologyReleasesPage from "@/pages/TerminologyReleasesPage.vue";
import TranslationProfilesPage from "@/pages/TranslationProfilesPage.vue";
import TranslationQaQueuePage from "@/pages/TranslationQaQueuePage.vue";
import TranslationResultQaPage from "@/pages/TranslationResultQaPage.vue";
import TranslationTermSetPage from "@/pages/TranslationTermSetPage.vue";
import UserManagementPage from "@/pages/UserManagementPage.vue";
import WordPageStyleDetailPage from "@/pages/WordPageStyleDetailPage.vue";
import WordPageStyleListPage from "@/pages/WordPageStyleListPage.vue";
import { getDefaultProtectedRoute, type AppAccessContext } from "@/navigation/appShell";
import { pinia } from "@/stores";
import { useAuthStore } from "@/stores/auth";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: "/login",
      name: "login",
      component: LoginPage,
      meta: { public: true },
    },
    {
      path: "/",
      component: AppLayout,
      meta: { requiresAuth: true },
      children: [
        { path: "", name: "protected-root", component: OperationsCockpitPage },
        { path: "cockpit", name: "cockpit", component: OperationsCockpitPage },
        { path: "forbidden", name: "forbidden", component: ForbiddenPage },
        { path: "jobs", name: "jobs", component: JobsPage, meta: { permissions: ["document_jobs:read"] } },
        { path: "incidents", name: "incidents", component: IncidentTriagePage, meta: { permissions: ["document_jobs:read"] } },
        { path: "jobs/new", name: "job-create", component: JobCreatePage, meta: { permissions: ["document_jobs:create"] } },
        { path: "jobs/:jobId", name: "job-detail", component: JobDetailPage, props: true, meta: { permissions: ["document_jobs:read"] } },
        {
          path: "jobs/:jobId/translation-qa",
          name: "job-translation-qa",
          component: TranslationResultQaPage,
          props: true,
          meta: { permissions: ["translation_qa:read"] },
        },
        { path: "translation-qa", name: "translation-qa", component: TranslationQaQueuePage, meta: { permissions: ["translation_qa:read"] } },
        { path: "settings", name: "settings", component: SettingsHomePage, meta: { permissions: ["settings:read"] } },
        { path: "settings/templates", name: "settings-templates", component: TemplateListPage, meta: { roles: ["admin"], permissions: ["settings:read"] } },
        {
          path: "settings/word-page-styles",
          name: "settings-word-page-styles",
          component: WordPageStyleListPage,
          meta: { roles: ["admin"], permissions: ["settings:read"] },
        },
        {
          path: "settings/word-page-styles/:templateId",
          name: "settings-word-page-style-detail",
          component: WordPageStyleDetailPage,
          props: true,
          meta: { roles: ["admin"], permissions: ["settings:read"] },
        },
        {
          path: "settings/term-rule-sets",
          name: "settings-term-rule-sets",
          component: TermRuleSetPage,
          meta: { permissions: ["settings:read"] },
        },
        {
          path: "settings/terminology-releases",
          name: "settings-terminology-releases",
          component: TerminologyReleasesPage,
          meta: { permissions: ["settings:read"] },
        },
        {
          path: "settings/term-rules",
          name: "settings-term-rules",
          component: TermRuleWorkbenchPage,
          meta: { permissions: ["term_proposals:read"] },
        },
        {
          path: "settings/translation-profiles",
          name: "settings-translation-profiles",
          component: TranslationProfilesPage,
          meta: { permissions: ["settings:read"] },
        },
        {
          path: "settings/translation-term-sets",
          name: "settings-translation-term-sets",
          component: TranslationTermSetPage,
          meta: { permissions: ["settings:read"] },
        },
        {
          path: "settings/templates/:templateId",
          name: "settings-template-detail",
          component: TemplateDetailPage,
          props: true,
          meta: { roles: ["admin"], permissions: ["settings:read"] },
        },
        {
          path: "term-rule-reviews",
          name: "term-rule-reviews",
          component: TermRuleReviewFlowPage,
          meta: { permissions: ["term_proposals:read"] },
        },
        { path: "term-proposals", name: "term-proposals", component: TermProposalsPage, meta: { permissions: ["term_proposals:read"] } },
        { path: "system-status", name: "system-status", component: SystemStatusPage, meta: { permissions: ["system:read"] } },
        {
          path: "system-status/ops-dashboard",
          name: "system-status-ops-dashboard",
          component: OpsDashboardPage,
          meta: { permissions: ["ops:read"] },
        },
        {
          path: "system-status/acceptance",
          name: "system-status-acceptance",
          component: AcceptanceCenterPage,
          meta: { roles: ["admin"], permissions: ["ops:read"] },
        },
        {
          path: "system-status/audit-events",
          name: "system-status-audit-events",
          component: AuditLogPage,
          meta: { permissions: ["audit:read"] },
        },
        {
          path: "system-status/users",
          name: "system-status-users",
          component: UserManagementPage,
          meta: { roles: ["admin"], permissions: ["users:manage"] },
        },
        {
          path: "system-status/file-retention",
          name: "system-status-file-retention",
          component: FileRetentionPage,
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
