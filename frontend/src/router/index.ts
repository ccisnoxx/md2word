// File: frontend/src/router/index.ts
// Purpose: Define static internal portal/Admin routes and the auth guard.
import { createRouter, createWebHistory, type RouteLocationNormalized } from "vue-router";

import { setUnauthorizedHandler } from "@/api/client";
import AppLayout from "@/layouts/AppLayout.vue";
import AuditLogPage from "@/pages/AuditLogPage.vue";
import FileRetentionPage from "@/pages/FileRetentionPage.vue";
import JobDetailPage from "@/pages/JobDetailPage.vue";
import JobsPage from "@/pages/JobsPage.vue";
import LoginPage from "@/pages/LoginPage.vue";
import OpsDashboardPage from "@/pages/OpsDashboardPage.vue";
import SettingsHomePage from "@/pages/SettingsHomePage.vue";
import SystemStatusPage from "@/pages/SystemStatusPage.vue";
import TemplateDetailPage from "@/pages/TemplateDetailPage.vue";
import TemplateListPage from "@/pages/TemplateListPage.vue";
import TermRuleWorkbenchPage from "@/pages/TermRuleWorkbenchPage.vue";
import TermRuleSetPage from "@/pages/TermRuleSetPage.vue";
import TermProposalsPage from "@/pages/TermProposalsPage.vue";
import TranslationProfilesPage from "@/pages/TranslationProfilesPage.vue";
import TranslationQaQueuePage from "@/pages/TranslationQaQueuePage.vue";
import TranslationResultQaPage from "@/pages/TranslationResultQaPage.vue";
import TranslationTermSetPage from "@/pages/TranslationTermSetPage.vue";
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
        { path: "", redirect: "/jobs" },
        { path: "jobs", name: "jobs", component: JobsPage },
        { path: "jobs/:jobId", name: "job-detail", component: JobDetailPage, props: true },
        { path: "jobs/:jobId/translation-qa", name: "job-translation-qa", component: TranslationResultQaPage, props: true },
        { path: "translation-qa", name: "translation-qa", component: TranslationQaQueuePage },
        { path: "settings", name: "settings", component: SettingsHomePage, meta: { roles: ["admin"] } },
        { path: "settings/templates", name: "settings-templates", component: TemplateListPage, meta: { roles: ["admin"] } },
        {
          path: "settings/term-rule-sets",
          name: "settings-term-rule-sets",
          component: TermRuleSetPage,
          meta: { roles: ["admin"] },
        },
        {
          path: "settings/term-rules",
          name: "settings-term-rules",
          component: TermRuleWorkbenchPage,
          meta: { roles: ["admin"] },
        },
        {
          path: "settings/translation-profiles",
          name: "settings-translation-profiles",
          component: TranslationProfilesPage,
          meta: { roles: ["admin"] },
        },
        {
          path: "settings/translation-term-sets",
          name: "settings-translation-term-sets",
          component: TranslationTermSetPage,
          meta: { roles: ["admin"] },
        },
        {
          path: "settings/templates/:templateId",
          name: "settings-template-detail",
          component: TemplateDetailPage,
          props: true,
          meta: { roles: ["admin"] },
        },
        { path: "term-proposals", name: "term-proposals", component: TermProposalsPage },
        { path: "system-status", name: "system-status", component: SystemStatusPage, meta: { roles: ["admin"] } },
        {
          path: "system-status/ops-dashboard",
          name: "system-status-ops-dashboard",
          component: OpsDashboardPage,
          meta: { roles: ["admin"] },
        },
        {
          path: "system-status/audit-events",
          name: "system-status-audit-events",
          component: AuditLogPage,
          meta: { roles: ["admin"] },
        },
        {
          path: "system-status/file-retention",
          name: "system-status-file-retention",
          component: FileRetentionPage,
          meta: { roles: ["admin"] },
        },
      ],
    },
    {
      path: "/:pathMatch(.*)*",
      redirect: "/jobs",
    },
  ],
});

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

function routeRoles(to: RouteLocationNormalized): string[] {
  if (!Array.isArray(to.meta.roles)) {
    return [];
  }
  return to.meta.roles.filter((role): role is string => typeof role === "string");
}

router.beforeEach(async (to) => {
  const auth = useAuthStore(pinia);
  const isPublic = Boolean(to.meta.public);

  if (to.path === "/login" && auth.token) {
    try {
      if (!auth.user) {
        await auth.loadCurrentUser();
      }
      return "/jobs";
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

  const allowedRoles = routeRoles(to);
  if (allowedRoles.length > 0 && !allowedRoles.includes(auth.user?.role ?? "")) {
    return "/jobs";
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
