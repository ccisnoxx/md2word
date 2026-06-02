<!-- frontend/src/layouts/AppLayout.vue: Protected workbench layout with compact header navigation. -->
<template>
  <el-container class="app-layout">
    <el-header class="app-header">
      <div class="brand">
        <router-link class="brand-link" to="/jobs">内部文档转换工作台</router-link>
        <el-tag size="small" effect="plain">MVP</el-tag>
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

    <el-main class="app-main">
      <router-view />
    </el-main>
  </el-container>
</template>

<script setup lang="ts">
import { SwitchButton } from "@element-plus/icons-vue";
import { useRouter } from "vue-router";

import { useAuthStore } from "@/stores/auth";

const auth = useAuthStore();
const router = useRouter();
const navItems = [
  { label: "任务工作台", to: "/jobs" },
  { label: "配置中心", to: "/settings" },
  { label: "术语建议", to: "/term-proposals" },
];

function handleLogout(): void {
  auth.logout();
  void router.push("/login");
}
</script>

<style scoped lang="scss">
.app-layout {
  min-height: 100vh;
  background: #f5f7fb;
  color-scheme: light;
}

.app-header {
  position: sticky;
  top: 0;
  z-index: 10;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  height: 58px;
  padding: 0 24px;
  border-bottom: 1px solid rgba(217, 226, 236, 0.86);
  background: rgba(255, 255, 255, 0.86);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
}

.brand,
.main-nav,
.header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.brand-link {
  color: #111827;
  font-size: 16px;
  font-weight: 700;
}

.main-nav {
  flex: 1;
  justify-content: center;
}

.main-nav a {
  padding: 8px 10px;
  border-radius: 8px;
  color: #475467;
  font-size: 14px;
  font-weight: 600;
}

.main-nav a.router-link-active {
  background: #eff6ff;
  color: #1d4ed8;
}

.user-text {
  font-size: 14px;
  color: #344054;
}

.app-main {
  width: min(1280px, 100%);
  margin: 0 auto;
  padding: 20px 24px 36px;
}

@media (prefers-color-scheme: dark) {
  .app-layout {
    background: #050711;
    color-scheme: dark;
  }

  .app-header {
    border-bottom-color: rgba(148, 163, 184, 0.18);
    background: rgba(5, 7, 17, 0.82);
  }

  .brand-link {
    color: #f8fafc;
  }

  .main-nav a {
    color: #cbd5e1;
  }

  .main-nav a.router-link-active {
    background: rgba(37, 99, 235, 0.22);
    color: #bfdbfe;
  }

  .user-text {
    color: #cbd5e1;
  }
}

@media (max-width: 720px) {
  .app-header {
    align-items: flex-start;
    flex-direction: column;
    height: auto;
    padding: 12px 16px;
  }

  .main-nav {
    justify-content: flex-start;
    overflow-x: auto;
    width: 100%;
  }

  .app-main {
    padding: 16px;
  }
}
</style>
