<!-- frontend/src/layouts/AppLayout.vue: Protected workbench shell with sidebar navigation and compact topbar. -->
<template>
  <div class="app-layout" :class="{ 'is-sidebar-collapsed': sidebarCollapsed }">
    <aside class="app-sidebar-shell" aria-label="主导航">
      <AppSidebar
        :groups="navGroups"
        :active-group-id="routeContext.groupId"
        :active-item-id="routeContext.itemId"
        :brand-to="defaultProtectedRoute"
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
        :brand-to="defaultProtectedRoute"
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
          <el-button class="topbar-command" :icon="Search" aria-label="打开命令面板" @click="openCommandPalette">
            <span>搜索</span>
            <kbd>Cmd/Ctrl+K</kbd>
          </el-button>
          <AppThemeToggle />
          <span class="topbar-user" aria-label="当前用户">
            <span class="topbar-user-name">{{ userDisplayName }}</span>
            <span v-if="userRoleLabel" class="topbar-user-role">{{ userRoleLabel }}</span>
          </span>
          <el-button class="topbar-change-password" :icon="Lock" text @click="openChangePasswordDialog">修改密码</el-button>
          <el-button class="topbar-logout" :icon="SwitchButton" text @click="handleLogout">退出</el-button>
        </div>
      </header>

      <el-main class="app-main">
        <router-view />
      </el-main>
    </div>

    <OperatorCommandPalette ref="commandPaletteRef" :access="access" />

    <el-dialog
      v-model="changePasswordDialogVisible"
      title="修改密码"
      width="min(520px, calc(100vw - 32px))"
      top="24px"
      class="password-dialog"
      append-to="body"
      :append-to-body="true"
    >
      <div class="password-dialog-scroll">
        <ApiErrorAlert :error="changePasswordError" />
        <el-form label-position="top">
          <el-form-item label="当前密码">
            <el-input
              v-model="changePasswordForm.current_password"
              type="password"
              show-password
              autocomplete="current-password"
            />
          </el-form-item>
          <el-form-item label="新密码">
            <el-input
              v-model="changePasswordForm.new_password"
              type="password"
              show-password
              autocomplete="new-password"
            />
          </el-form-item>
          <el-form-item label="确认新密码">
            <el-input
              v-model="changePasswordForm.confirm_password"
              type="password"
              show-password
              autocomplete="new-password"
            />
          </el-form-item>
        </el-form>
      </div>
      <template #footer>
        <el-button @click="changePasswordDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="changingPassword" @click="submitChangePassword">确认修改</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from "vue";
import { ElMessage } from "element-plus";
import { Lock, Menu, Search, SwitchButton } from "@element-plus/icons-vue";
import { useRoute, useRouter } from "vue-router";

import { authApi } from "@/api/auth";
import AppBreadcrumb from "@/components/AppBreadcrumb.vue";
import ApiErrorAlert from "@/components/ApiErrorAlert.vue";
import AppSidebar from "@/components/AppSidebar.vue";
import AppThemeToggle from "@/components/AppThemeToggle.vue";
import OperatorCommandPalette from "@/components/OperatorCommandPalette.vue";
import { getAppNavigationGroups, getAppRouteContext, getDefaultProtectedRoute, type AppAccessContext } from "@/navigation/appShell";
import { useAuthStore } from "@/stores/auth";
import { normalizeApiError, type ApiClientError } from "@/utils/errors";
import { getStoredSidebarCollapsed, persistSidebarCollapsed } from "@/utils/sidebarState";

const auth = useAuthStore();
const route = useRoute();
const router = useRouter();
const sidebarCollapsed = ref(getStoredSidebarCollapsed());
const mobileDrawerOpen = ref(false);
const commandPaletteRef = ref<InstanceType<typeof OperatorCommandPalette> | null>(null);
const changePasswordDialogVisible = ref(false);
const changingPassword = ref(false);
const changePasswordError = ref<ApiClientError | null>(null);
const changePasswordForm = reactive({
  current_password: "",
  new_password: "",
  confirm_password: "",
});

const access = computed<AppAccessContext>(() => ({
  role: auth.user?.role ?? null,
  roles: auth.user?.roles ?? [],
  permissions: auth.user?.permissions ?? [],
}));
const navGroups = computed(() => getAppNavigationGroups(access.value));
const routeContext = computed(() => getAppRouteContext(route, access.value));
const defaultProtectedRoute = computed(() => getDefaultProtectedRoute(access.value));
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

function openCommandPalette(): void {
  commandPaletteRef.value?.show();
}

function handleSidebarNavigate(): void {
  mobileDrawerOpen.value = false;
}

function handleLogout(): void {
  auth.logout();
  void router.push("/login");
}

function openChangePasswordDialog(): void {
  changePasswordForm.current_password = "";
  changePasswordForm.new_password = "";
  changePasswordForm.confirm_password = "";
  changePasswordError.value = null;
  changePasswordDialogVisible.value = true;
}

async function submitChangePassword(): Promise<void> {
  if (changePasswordForm.new_password !== changePasswordForm.confirm_password) {
    changePasswordError.value = null;
    ElMessage.error("两次输入的新密码不一致。");
    return;
  }
  changingPassword.value = true;
  changePasswordError.value = null;
  try {
    await authApi.changePassword({
      current_password: changePasswordForm.current_password,
      new_password: changePasswordForm.new_password,
    });
    ElMessage.success("密码已修改，请重新登录。");
    changePasswordDialogVisible.value = false;
    auth.logout();
    void router.push({ path: "/login", query: { auth: "password_changed" } });
  } catch (caught) {
    changePasswordError.value = normalizeApiError(caught);
    ElMessage.error(changePasswordError.value.message);
  } finally {
    changingPassword.value = false;
  }
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

.topbar-command {
  flex: 0 0 auto;
}

.topbar-command kbd {
  display: inline-grid;
  min-height: 18px;
  margin-left: 6px;
  place-items: center;
  padding: 0 6px;
  border: 1px solid var(--app-color-border);
  border-radius: var(--app-radius-sm);
  background: var(--app-color-surface-muted);
  color: var(--app-color-text-muted);
  font-family: var(--app-font-mono);
  font-size: 11px;
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

.topbar-change-password {
  flex: 0 0 auto;
}

.app-main {
  overflow: visible;
  min-width: 0;
  width: 100%;
  padding: var(--app-space-6) var(--app-space-6) 40px;
}

:deep(.password-dialog) {
  display: flex;
  flex-direction: column;
  max-height: calc(100vh - 48px);
  max-height: calc(100dvh - 48px);
  margin-bottom: 24px;
}

:deep(.password-dialog .el-dialog__header),
:deep(.password-dialog .el-dialog__footer) {
  flex: 0 0 auto;
}

:deep(.password-dialog .el-dialog__body) {
  flex: 1 1 auto;
  min-height: 0;
  overflow: hidden;
}

.password-dialog-scroll {
  max-height: min(520px, calc(100vh - 220px));
  max-height: min(520px, calc(100dvh - 220px));
  overflow-y: auto;
  overscroll-behavior: contain;
  padding-right: 4px;
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

  .topbar-command :deep(span),
  .topbar-command kbd {
    display: none;
  }

  .topbar-user {
    max-width: 118px;
    padding: 0 var(--app-space-2);
  }

  .topbar-user-role,
  .topbar-change-password :deep(span),
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
