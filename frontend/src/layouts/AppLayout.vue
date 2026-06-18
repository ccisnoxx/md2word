<!-- frontend/src/layouts/AppLayout.vue: Protected workbench layout with compact header navigation. -->
<template>
  <el-container class="app-layout">
    <el-header class="app-header">
      <div class="brand">
        <router-link class="brand-link" to="/jobs">
          <span class="brand-mark" aria-hidden="true">
            <el-icon><DocumentChecked /></el-icon>
          </span>
          <span class="brand-copy">
            <strong>md2word</strong>
            <small>内部文档转换工作台</small>
          </span>
        </router-link>
        <el-tag size="small" effect="plain">内部门户</el-tag>
      </div>
      <nav class="main-nav" aria-label="主导航">
        <router-link v-for="item in navItems" :key="item.to" :to="item.to">
          {{ item.label }}
        </router-link>
      </nav>
      <div class="header-actions">
        <span class="user-text">
          {{ auth.user?.display_name || auth.user?.username || "未命名用户" }}
          <span v-if="auth.user?.role" class="muted">({{ auth.user.role }})</span>
        </span>
        <el-button :icon="SwitchButton" text @click="handleLogout">退出</el-button>
      </div>
    </el-header>

    <div class="breadcrumb-shell">
      <AppBreadcrumb />
    </div>

    <el-main class="app-main">
      <router-view />
    </el-main>
  </el-container>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { DocumentChecked, SwitchButton } from "@element-plus/icons-vue";
import { useRouter } from "vue-router";

import AppBreadcrumb from "@/components/AppBreadcrumb.vue";
import { useAuthStore } from "@/stores/auth";

const auth = useAuthStore();
const router = useRouter();

type NavItem = {
  label: string;
  to: string;
  permission?: string;
};

const navItems = computed<NavItem[]>(() => {
  const items: NavItem[] = [
    { label: "任务工作台", to: "/jobs", permission: "document_jobs:read" },
    { label: "翻译 QA", to: "/translation-qa", permission: "translation_qa:read" },
    { label: "配置中心", to: "/settings", permission: "settings:read" },
    {
      label: auth.hasPermission("term_proposals:review") ? "提案审核" : "术语建议",
      to: "/term-proposals",
      permission: "term_proposals:read",
    },
    { label: "系统状态", to: "/system-status", permission: "system:read" },
  ];
  return items.filter((item) => !item.permission || auth.hasPermission(item.permission));
});

function handleLogout(): void {
  auth.logout();
  void router.push("/login");
}
</script>

<style scoped lang="scss">
.app-layout {
  min-height: 100vh;
  background: var(--app-color-bg);
  color-scheme: light;
}

.app-header {
  position: sticky;
  top: 0;
  z-index: 10;
  display: grid;
  grid-template-columns: minmax(220px, 0.9fr) minmax(0, 1.4fr) minmax(220px, 0.9fr);
  align-items: center;
  gap: var(--app-space-4);
  height: var(--app-header-height);
  padding: 0 var(--app-space-6);
  border-bottom: 1px solid var(--app-color-border-soft);
  background: var(--app-color-surface-elevated);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
}

.brand,
.main-nav,
.header-actions {
  display: flex;
  align-items: center;
  gap: var(--app-space-2);
}

.brand-link {
  display: inline-flex;
  align-items: center;
  gap: var(--app-space-2);
  color: var(--app-color-text);
}

.brand-link:hover,
.brand-link:focus-visible {
  color: var(--app-color-text);
}

.brand-mark {
  display: inline-grid;
  width: 32px;
  height: 32px;
  place-items: center;
  border: 1px solid var(--app-color-primary-border);
  border-radius: var(--app-radius-md);
  background: var(--app-color-primary-soft);
  color: var(--app-color-primary-hover);
  font-size: 14px;
  font-weight: 800;
}

.brand-copy {
  display: grid;
  gap: 1px;
}

.brand-copy strong {
  color: var(--app-color-text);
  font-size: 15px;
  line-height: 1.1;
}

.brand-copy small {
  color: var(--app-color-text-muted);
  font-size: 12px;
  line-height: 1.2;
}

.main-nav {
  justify-content: center;
  min-width: 0;
}

.main-nav a {
  min-height: 34px;
  padding: var(--app-space-2) 10px;
  border: 1px solid transparent;
  border-radius: var(--app-radius-md);
  color: var(--app-color-text-muted);
  font-size: 14px;
  font-weight: 600;
  transition:
    background-color 160ms ease-out,
    color 160ms ease-out;
}

.main-nav a.router-link-active {
  border: 1px solid var(--app-color-primary-border);
  background: var(--app-color-primary-soft);
  color: var(--app-color-primary-hover);
}

.main-nav a:hover,
.main-nav a:focus-visible {
  background: var(--app-color-surface-muted);
  color: var(--app-color-primary-hover);
}

.header-actions {
  justify-content: flex-end;
  min-width: 0;
}

.user-text {
  min-width: 0;
  overflow: hidden;
  font-size: 14px;
  color: var(--app-color-text-muted);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.app-main {
  width: min(var(--app-content-wide), 100%);
  margin: 0 auto;
  padding: var(--app-space-5) var(--app-space-6) 40px;
}

.breadcrumb-shell {
  width: min(var(--app-content-wide), 100%);
  margin: 0 auto;
  padding: var(--app-space-3) var(--app-space-6) 0;
}

@media (prefers-color-scheme: dark) {
  .app-layout {
    background: var(--app-color-bg);
    color-scheme: dark;
  }

  .app-header {
    border-bottom-color: var(--app-color-border);
    background: var(--app-color-surface-elevated);
  }

  .brand-link {
    color: var(--app-color-text);
  }

  .main-nav a {
    color: var(--app-color-text-muted);
  }

  .main-nav a.router-link-active {
    background: var(--app-color-primary-soft);
    color: var(--app-color-primary-hover);
  }

  .user-text {
    color: var(--app-color-text-muted);
  }
}

@media (max-width: 980px) {
  .app-header {
    align-items: flex-start;
    grid-template-columns: 1fr;
    height: auto;
    padding: var(--app-space-3) var(--app-space-4);
  }

  .brand,
  .header-actions {
    width: 100%;
    justify-content: space-between;
  }

  .main-nav {
    justify-content: flex-start;
    overflow-x: auto;
    width: 100%;
    padding-bottom: 2px;
  }

  .main-nav a {
    flex: 0 0 auto;
  }
}

@media (max-width: 720px) {
  .app-main {
    padding: var(--app-space-4);
  }

  .breadcrumb-shell {
    padding: 10px var(--app-space-4) 0;
  }
}

@media (max-width: 520px) {
  .brand {
    align-items: flex-start;
    flex-direction: column;
  }

  .header-actions {
    align-items: flex-start;
    flex-direction: column;
  }

  .user-text {
    width: 100%;
  }
}
</style>
