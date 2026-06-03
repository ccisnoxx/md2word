// frontend/src/router/index.ts: Static MVP routes and auth guard.
import { createRouter, createWebHistory, type RouteLocationNormalized } from "vue-router";

import { setUnauthorizedHandler } from "@/api/client";
import AppLayout from "@/layouts/AppLayout.vue";
import JobDetailPage from "@/pages/JobDetailPage.vue";
import JobsPage from "@/pages/JobsPage.vue";
import LoginPage from "@/pages/LoginPage.vue";
import SettingsHomePage from "@/pages/SettingsHomePage.vue";
import TemplateDetailPage from "@/pages/TemplateDetailPage.vue";
import TemplateListPage from "@/pages/TemplateListPage.vue";
import TermRuleSetPage from "@/pages/TermRuleSetPage.vue";
import TermProposalsPage from "@/pages/TermProposalsPage.vue";
import TranslationProfilesPage from "@/pages/TranslationProfilesPage.vue";
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
        { path: "settings", name: "settings", component: SettingsHomePage },
        { path: "settings/templates", name: "settings-templates", component: TemplateListPage },
        { path: "settings/term-rule-sets", name: "settings-term-rule-sets", component: TermRuleSetPage },
        {
          path: "settings/translation-profiles",
          name: "settings-translation-profiles",
          component: TranslationProfilesPage,
        },
        {
          path: "settings/templates/:templateId",
          name: "settings-template-detail",
          component: TemplateDetailPage,
          props: true,
        },
        { path: "term-proposals", name: "term-proposals", component: TermProposalsPage },
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
