<!-- frontend/src/layouts/AppLayout.vue: Protected workbench shell with sidebar navigation and compact topbar. -->
<template>
  <div class="app-layout" :class="{ 'is-sidebar-collapsed': sidebarCollapsed }">
    <aside class="app-sidebar-shell" aria-label="主导航">
      <AppSidebar
        :groups="navGroups"
        :active-group-id="routeContext.groupId"
        :active-item-id="routeContext.itemId"
        :collapsed="sidebarCollapsed"
        @navigate="handleSidebarNavigate"
        @toggle-collapse="toggleSidebarCollapsed"
      />
    </aside>

    <el-drawer
      v-model="mobileDrawerOpen"
      class="app-mobile-drawer"
      direction="ltr"
      size="304px"
      :append-to-body="true"
      :with-header="false"
    >
      <AppSidebar
        :groups="navGroups"
        :active-group-id="routeContext.groupId"
        :active-item-id="routeContext.itemId"
        mobile
        @navigate="handleSidebarNavigate"
      />
    </el-drawer>

    <div class="app-workbench">
      <header class="app-topbar">
        <div class="topbar-context">
          <el-button class="topbar-menu-button" :icon="Menu" aria-label="打开导航" circle @click="openMobileDrawer" />
          <div class="topbar-copy">
            <span class="topbar-module">{{ routeContext.moduleLabel }}</span>
            <strong class="topbar-page">{{ routeContext.pageLabel }}</strong>
            <AppBreadcrumb class="topbar-breadcrumb" :items="routeContext.breadcrumbs" />
          </div>
        </div>

        <div class="topbar-actions">
          <AppThemeToggle />
          <span class="topbar-user" aria-label="当前用户">
            <span class="topbar-user-name">{{ userDisplayName }}</span>
            <span v-if="userRoleLabel" class="topbar-user-role">{{ userRoleLabel }}</span>
          </span>
          <el-button class="topbar-logout" :icon="SwitchButton" text @click="handleLogout">退出</el-button>
        </div>
      </header>

      <el-main class="app-main">
        <router-view />
      </el-main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { Menu, SwitchButton } from "@element-plus/icons-vue";
import { useRoute, useRouter } from "vue-router";

import AppBreadcrumb from "@/components/AppBreadcrumb.vue";
import AppSidebar from "@/components/AppSidebar.vue";
import AppThemeToggle from "@/components/AppThemeToggle.vue";
import { getAppNavigationGroups, getAppRouteContext, type AppAccessContext } from "@/navigation/appShell";
import { useAuthStore } from "@/stores/auth";
import { getStoredSidebarCollapsed, persistSidebarCollapsed } from "@/utils/sidebarState";

const auth = useAuthStore();
const route = useRoute();
const router = useRouter();
const sidebarCollapsed = ref(getStoredSidebarCollapsed());
const mobileDrawerOpen = ref(false);

const access = computed<AppAccessContext>(() => ({
  role: auth.user?.role ?? null,
  roles: auth.user?.roles ?? [],
  permissions: auth.user?.permissions ?? [],
}));
const navGroups = computed(() => getAppNavigationGroups(access.value));
const routeContext = computed(() => getAppRouteContext(route, access.value));
const userDisplayName = computed(() => auth.user?.display_name || auth.user?.username || "未命名用户");
const userRoleLabel = computed(() => auth.user?.role || "");

watch(
  () => route.fullPath,
  () => {
    mobileDrawerOpen.value = false;
  },
);

function toggleSidebarCollapsed(): void {
  sidebarCollapsed.value = !sidebarCollapsed.value;
  persistSidebarCollapsed(sidebarCollapsed.value);
}

function openMobileDrawer(): void {
  mobileDrawerOpen.value = true;
}

function handleSidebarNavigate(): void {
  mobileDrawerOpen.value = false;
}

function handleLogout(): void {
  auth.logout();
  void router.push("/login");
}
</script>

<style scoped lang="scss">
.app-layout {
  display: grid;
  grid-template-columns: var(--app-sidebar-width, 280px) minmax(0, 1fr);
  min-height: 100vh;
  background: var(--app-color-bg);
  color-scheme: var(--app-color-scheme);
  transition: grid-template-columns var(--app-motion-base) var(--app-ease-out);
}

.app-layout.is-sidebar-collapsed {
  grid-template-columns: var(--app-sidebar-collapsed-width, 76px) minmax(0, 1fr);
}

.app-sidebar-shell {
  position: sticky;
  top: 0;
  z-index: 30;
  height: 100vh;
  min-width: 0;
  border-right: 1px solid color-mix(in srgb, #334155 72%, transparent);
  box-shadow: 14px 0 34px rgba(15, 23, 42, 0.08);
}

.app-workbench {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  min-width: 0;
  min-height: 100vh;
}

.app-topbar {
  position: sticky;
  top: 0;
  z-index: 20;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--app-space-4);
  min-width: 0;
  min-height: var(--app-header-height);
  padding: 10px var(--app-space-6);
  border-bottom: 1px solid var(--app-color-border-soft);
  background: color-mix(in srgb, var(--app-color-surface-elevated) 92%, transparent);
  box-shadow: 0 8px 24px rgba(30, 27, 75, 0.06);
  backdrop-filter: blur(14px) saturate(1.08);
  -webkit-backdrop-filter: blur(14px) saturate(1.08);
}

.topbar-context,
.topbar-actions {
  display: flex;
  align-items: center;
  min-width: 0;
}

.topbar-context {
  gap: var(--app-space-3);
}

.topbar-actions {
  justify-content: flex-end;
  gap: var(--app-space-2);
}

.topbar-menu-button {
  display: none;
  flex: 0 0 auto;
  border-color: var(--app-color-border-soft);
  background: var(--app-color-surface);
  color: var(--app-color-primary-hover);
}

.topbar-copy {
  display: grid;
  align-content: center;
  gap: 2px;
  min-width: 0;
}

.topbar-module {
  overflow: hidden;
  color: var(--app-color-text-faint);
  font-size: 12px;
  font-weight: 760;
  line-height: 1.1;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.topbar-page {
  overflow: hidden;
  color: var(--app-color-text);
  font-size: 18px;
  line-height: 1.2;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.topbar-breadcrumb {
  min-width: 0;
}

.topbar-user {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  max-width: 260px;
  min-height: 34px;
  padding: 0 var(--app-space-3);
  border: 1px solid var(--app-color-border-soft);
  border-radius: var(--app-radius-pill);
  background: var(--app-color-surface);
  color: var(--app-color-text-muted);
  font-size: 13px;
  font-weight: 650;
}

.topbar-user-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.topbar-user-role {
  flex: 0 0 auto;
  color: var(--app-color-primary-hover);
  font-size: 12px;
}

.topbar-logout {
  flex: 0 0 auto;
}

.app-main {
  overflow: visible;
  min-width: 0;
  width: 100%;
  padding: var(--app-space-6) var(--app-space-6) 40px;
}

:global(.app-mobile-drawer.el-drawer) {
  background: #0f172a;
}

:global(.app-mobile-drawer .el-drawer__body) {
  height: 100%;
  padding: 0;
}

@media (max-width: 980px) {
  .app-layout,
  .app-layout.is-sidebar-collapsed {
    display: block;
  }

  .app-sidebar-shell {
    display: none;
  }

  .app-workbench {
    min-height: 100vh;
  }

  .app-topbar {
    align-items: flex-start;
    min-height: auto;
    padding: var(--app-space-3) var(--app-space-4);
  }

  .topbar-menu-button {
    display: inline-flex;
  }

  .topbar-actions {
    flex: 0 0 auto;
  }

  .app-main {
    padding: var(--app-space-4);
  }
}

@media (max-width: 640px) {
  .app-topbar {
    gap: var(--app-space-3);
  }

  .topbar-context {
    flex: 1 1 auto;
  }

  .topbar-actions {
    gap: 6px;
  }

  .topbar-user {
    max-width: 118px;
    padding: 0 var(--app-space-2);
  }

  .topbar-user-role,
  .topbar-logout :deep(span) {
    display: none;
  }

  .topbar-page {
    font-size: 16px;
  }
}

@media (max-width: 460px) {
  .topbar-breadcrumb {
    display: none;
  }
}
</style>
