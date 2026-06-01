// frontend/src/router/index.ts: Static MVP routes and auth guard.
import { createRouter, createWebHistory, type RouteLocationNormalized } from "vue-router";

import { setUnauthorizedHandler } from "@/api/client";
import AppLayout from "@/layouts/AppLayout.vue";
import JobDetailPage from "@/pages/JobDetailPage.vue";
import JobsPage from "@/pages/JobsPage.vue";
import LoginPage from "@/pages/LoginPage.vue";
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
      ],
    },
    {
      path: "/:pathMatch(.*)*",
      redirect: "/jobs",
    },
  ],
});

function loginRedirect(to: RouteLocationNormalized): { path: string; query: Record<string, string> } {
  return {
    path: "/login",
    query: to.fullPath === "/login" ? {} : { redirect: to.fullPath },
  };
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
    } catch {
      auth.logout();
      return loginRedirect(to);
    }
  }

  return true;
});

setUnauthorizedHandler(() => {
  const auth = useAuthStore(pinia);
  auth.logout();
  if (router.currentRoute.value.path !== "/login") {
    void router.push(loginRedirect(router.currentRoute.value));
  }
});

export default router;
