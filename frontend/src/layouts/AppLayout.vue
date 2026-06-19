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
            <small>PDF → DOCX · QA · Audit</small>
          </span>
        </router-link>
        <el-tag size="small" effect="plain">文档交付</el-tag>
      </div>
      <nav class="main-nav" aria-label="主导航">
        <router-link v-for="item in navItems" :key="item.to" :to="item.to">
          <el-icon aria-hidden="true"><component :is="item.icon" /></el-icon>
          <span>{{ item.label }}</span>
        </router-link>
      </nav>
      <div class="workflow-strip" aria-label="文档工作流">
        <span>PDF</span>
        <i aria-hidden="true"></i>
        <span>DOCX</span>
        <span>QA</span>
        <span>Audit</span>
      </div>
      <div class="header-actions">
        <AppThemeToggle />
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
import { computed, type Component } from "vue";
import {
  DocumentChecked,
  Files,
  Reading,
  Setting,
  Stamp,
  Monitor,
  SwitchButton,
} from "@element-plus/icons-vue";
import { useRouter } from "vue-router";

import AppBreadcrumb from "@/components/AppBreadcrumb.vue";
import AppThemeToggle from "@/components/AppThemeToggle.vue";
import { useAuthStore } from "@/stores/auth";

const auth = useAuthStore();
const router = useRouter();

type NavItem = {
  label: string;
  to: string;
  icon: Component;
  permission?: string;
};

const navItems = computed<NavItem[]>(() => {
  const items: NavItem[] = [
    { label: "任务工作台", to: "/jobs", icon: Files, permission: "document_jobs:read" },
    { label: "翻译 QA", to: "/translation-qa", icon: Reading, permission: "translation_qa:read" },
    { label: "配置中心", to: "/settings", icon: Setting, permission: "settings:read" },
    {
      label: auth.hasPermission("term_proposals:review") ? "提案审核" : "术语建议",
      to: "/term-proposals",
      icon: Stamp,
      permission: "term_proposals:read",
    },
    { label: "系统状态", to: "/system-status", icon: Monitor, permission: "system:read" },
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
  background: transparent;
  color-scheme: var(--app-color-scheme);
}

.app-header {
  position: sticky;
  top: 12px;
  z-index: 10;
  display: grid;
  grid-template-columns: minmax(230px, 0.78fr) minmax(520px, 1.58fr) auto minmax(210px, 0.64fr);
  align-items: center;
  gap: var(--app-space-3);
  width: min(calc(100% - 32px), var(--app-content-wide));
  min-height: calc(var(--app-header-height) + 8px);
  margin: 12px auto 0;
  padding: 0 var(--app-space-6);
  border: 1px solid color-mix(in srgb, var(--app-color-primary-border) 74%, transparent);
  border-radius: var(--app-radius-lg);
  background:
    linear-gradient(135deg, color-mix(in srgb, var(--app-color-surface-elevated) 82%, var(--app-color-primary-soft)), var(--app-color-glass-muted)),
    var(--app-gradient-glass);
  box-shadow:
    0 18px 42px color-mix(in srgb, var(--app-color-primary) 16%, transparent),
    var(--app-shadow-panel);
  backdrop-filter: var(--app-backdrop-panel);
  -webkit-backdrop-filter: var(--app-backdrop-panel);
}

.app-header::before {
  position: absolute;
  inset: 0 0 auto;
  height: 3px;
  content: "";
  background: var(--app-gradient-accent-line);
}

.app-header::after {
  position: absolute;
  inset: 3px 3px auto;
  height: 1px;
  content: "";
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.72), transparent);
  pointer-events: none;
}

.brand,
.main-nav,
.workflow-strip,
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
  width: 42px;
  height: 42px;
  place-items: center;
  border: 1px solid rgba(255, 255, 255, 0.32);
  border-radius: var(--app-radius-md);
  background: var(--app-gradient-action);
  color: #ffffff;
  box-shadow: 0 10px 22px color-mix(in srgb, var(--app-color-primary) 28%, transparent);
  font-size: 18px;
  font-weight: 800;
}

.brand-copy {
  display: grid;
  gap: 1px;
}

.brand-copy strong {
  color: var(--app-color-text);
  font-size: 16px;
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
  position: relative;
  overflow: hidden;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 38px;
  padding: var(--app-space-2) 12px;
  border: 1px solid transparent;
  border-radius: var(--app-radius-md);
  color: var(--app-color-text-muted);
  font-size: 14px;
  font-weight: 600;
  white-space: nowrap;
  transition:
    border-color var(--app-motion-fast) ease-out,
    background-color var(--app-motion-fast) ease-out,
    color var(--app-motion-fast) ease-out,
    transform var(--app-motion-fast) ease-out,
    box-shadow var(--app-motion-fast) ease-out;
}

.main-nav a .el-icon {
  font-size: 15px;
}

.main-nav a.router-link-active {
  border: 1px solid color-mix(in srgb, var(--app-color-primary-border) 76%, transparent);
  background: var(--app-gradient-action);
  color: #ffffff;
  box-shadow:
    0 10px 24px color-mix(in srgb, var(--app-color-primary) 22%, transparent),
    inset 0 1px 0 rgba(255, 255, 255, 0.34);
}

.main-nav a.router-link-active::after {
  position: absolute;
  inset: auto 10px 4px;
  height: 2px;
  border-radius: var(--app-radius-pill);
  content: "";
  background: linear-gradient(90deg, var(--app-color-accent-cyan), var(--app-color-accent-emerald));
  transition: opacity var(--app-motion-fast) ease-out;
}

.main-nav a:hover,
.main-nav a:focus-visible {
  background: color-mix(in srgb, var(--app-color-primary-soft) 64%, var(--app-color-glass-strong));
  color: var(--app-color-primary-hover);
  transform: translateY(-2px);
  box-shadow: 0 10px 22px color-mix(in srgb, var(--app-color-primary) 12%, transparent);
}

.main-nav a.router-link-active:hover,
.main-nav a.router-link-active:focus-visible {
  color: #ffffff;
}

.workflow-strip {
  justify-content: center;
  padding: 5px;
  border: 1px solid var(--app-color-border-soft);
  border-radius: var(--app-radius-pill);
  background:
    linear-gradient(90deg, color-mix(in srgb, var(--app-color-primary-soft) 72%, transparent), var(--app-color-glass)),
    var(--app-color-glass);
  color: var(--app-color-primary-rail);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.42),
    var(--app-shadow-subtle);
  white-space: nowrap;
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
}

.workflow-strip span {
  display: inline-grid;
  min-width: 38px;
  height: 24px;
  place-items: center;
  border-radius: var(--app-radius-pill);
  background: color-mix(in srgb, var(--app-color-glass-strong) 82%, var(--app-color-primary-soft));
  font-size: 11px;
  font-weight: 800;
}

.workflow-strip span:nth-last-child(2) {
  color: var(--app-color-accent-cyan);
}

.workflow-strip span:last-child {
  color: var(--app-color-accent-emerald);
}

.workflow-strip i {
  display: inline-block;
  width: 24px;
  height: 2px;
  border-radius: var(--app-radius-pill);
  background: var(--app-gradient-accent-line);
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
  padding: var(--app-space-6) var(--app-space-6) 40px;
}

.breadcrumb-shell {
  width: min(var(--app-content-wide), 100%);
  margin: 0 auto;
  padding: var(--app-space-3) var(--app-space-6) 0;
}

@media (prefers-color-scheme: dark) {
  .app-layout {
    background: transparent;
    color-scheme: var(--app-color-scheme);
  }

  .app-header {
    border-bottom-color: var(--app-color-border);
    background:
      linear-gradient(135deg, color-mix(in srgb, var(--app-color-surface-elevated) 82%, var(--app-color-primary-soft)), var(--app-color-glass-muted)),
      var(--app-gradient-glass);
  }

  .brand-link {
    color: var(--app-color-text);
  }

  .main-nav a {
    color: var(--app-color-text-muted);
  }

  .main-nav a.router-link-active {
    background: var(--app-gradient-action);
    color: #ffffff;
  }

  .workflow-strip {
    background: var(--app-color-glass);
  }

  .workflow-strip span {
    background: var(--app-color-glass-strong);
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
    width: calc(100% - 24px);
    margin-top: 10px;
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

  .workflow-strip {
    justify-content: flex-start;
    overflow-x: auto;
    width: 100%;
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
