<!-- frontend/src/pages/ForbiddenPage.vue: Explain route-level permission denial. -->
<template>
  <main class="forbidden-page" aria-labelledby="forbidden-title">
    <section class="forbidden-panel">
      <div class="icon-shell" aria-hidden="true">
        <el-icon><Lock /></el-icon>
      </div>
      <p class="eyebrow">403 Forbidden</p>
      <h1 id="forbidden-title">当前账号没有访问权限</h1>
      <p class="summary">该页面需要额外权限。请切换账号，或联系管理员确认角色和权限配置。</p>

      <dl class="meta-list">
        <div>
          <dt>当前账号</dt>
          <dd>{{ auth.user?.display_name || auth.user?.username || "未知账号" }}</dd>
        </div>
        <div>
          <dt>当前角色</dt>
          <dd>{{ auth.user?.role || "未知角色" }}</dd>
        </div>
        <div v-if="fromPath">
          <dt>目标页面</dt>
          <dd>{{ fromPath }}</dd>
        </div>
        <div v-if="requiredPermissions">
          <dt>需要权限</dt>
          <dd>{{ requiredPermissions }}</dd>
        </div>
      </dl>

      <div class="actions">
        <el-button type="primary" :icon="Back" @click="goJobs">返回任务工作台</el-button>
        <el-button :icon="SwitchButton" @click="logout">切换账号</el-button>
      </div>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { Back, Lock, SwitchButton } from "@element-plus/icons-vue";
import { useRoute, useRouter } from "vue-router";

import { useAuthStore } from "@/stores/auth";

const auth = useAuthStore();
const route = useRoute();
const router = useRouter();

const fromPath = computed(() => (typeof route.query.from === "string" ? route.query.from : ""));
const requiredPermissions = computed(() => (typeof route.query.required === "string" ? route.query.required : ""));

function goJobs(): void {
  void router.push("/jobs");
}

function logout(): void {
  auth.logout();
  void router.push({
    path: "/login",
    query: fromPath.value ? { redirect: fromPath.value } : {},
  });
}
</script>

<style scoped lang="scss">
.forbidden-page {
  display: grid;
  min-height: calc(100vh - 128px);
  place-items: center;
  padding: 32px 16px;
}

.forbidden-panel {
  width: min(620px, 100%);
  padding: 28px;
  border: 1px solid #d8e0eb;
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 18px 40px rgba(15, 23, 42, 0.08);
}

.icon-shell {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  margin-bottom: 14px;
  border-radius: 8px;
  background: #fff7ed;
  color: #c2410c;
  font-size: 22px;
}

.eyebrow {
  margin: 0 0 6px;
  color: #c2410c;
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
}

h1 {
  margin: 0;
  color: #111827;
  font-size: 24px;
}

.summary {
  margin: 10px 0 18px;
  color: #475467;
  line-height: 1.7;
}

.meta-list {
  display: grid;
  gap: 10px;
  margin: 0 0 22px;
}

.meta-list div {
  display: grid;
  grid-template-columns: 88px minmax(0, 1fr);
  gap: 12px;
}

dt {
  color: #667085;
  font-size: 13px;
}

dd {
  overflow-wrap: anywhere;
  margin: 0;
  color: #1f2937;
  font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace;
  font-size: 13px;
}

.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}
</style>
