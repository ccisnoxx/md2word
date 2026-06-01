<!-- frontend/src/layouts/AppLayout.vue: Protected workbench layout with compact header navigation. -->
<template>
  <el-container class="app-layout">
    <el-header class="app-header">
      <div class="brand">
        <router-link class="brand-link" to="/jobs">内部文档转换工作台</router-link>
        <el-tag size="small" effect="plain">MVP</el-tag>
      </div>
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

function handleLogout(): void {
  auth.logout();
  void router.push("/login");
}
</script>

<style scoped lang="scss">
.app-layout {
  min-height: 100vh;
}

.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  height: 58px;
  padding: 0 24px;
  border-bottom: 1px solid #d9e2ec;
  background: #ffffff;
}

.brand,
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

.user-text {
  font-size: 14px;
  color: #344054;
}

.app-main {
  width: min(1180px, 100%);
  margin: 0 auto;
  padding: 20px 24px 36px;
}

@media (max-width: 720px) {
  .app-header {
    align-items: flex-start;
    flex-direction: column;
    height: auto;
    padding: 12px 16px;
  }

  .app-main {
    padding: 16px;
  }
}
</style>
