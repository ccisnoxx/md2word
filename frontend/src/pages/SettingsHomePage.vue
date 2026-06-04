<!-- frontend/src/pages/SettingsHomePage.vue: Configuration center landing page for V2.1 resources. -->
<template>
  <main class="settings-page" aria-labelledby="settings-title">
    <section class="page-heading">
      <div>
        <p class="page-kicker">Config Management</p>
        <h1 id="settings-title">配置中心</h1>
        <p>集中查看模板、术语规则集和翻译配置的发布待办与资源入口。</p>
      </div>
      <RoleGate>
        <el-tag type="warning" effect="plain">admin 操作已启用</el-tag>
      </RoleGate>
    </section>

    <ConfigTodoSummary :summary="summary" :loading="loading" :error="error" @refresh="loadSummary" />

    <section class="settings-grid" aria-label="配置资源入口">
      <router-link v-for="card in cards" :key="card.to" class="settings-card" :to="card.to">
        <span class="settings-card-icon" aria-hidden="true">
          <el-icon><component :is="card.icon" /></el-icon>
        </span>
        <span>
          <strong>{{ card.title }}</strong>
          <small>{{ card.description }}</small>
        </span>
      </router-link>
    </section>
  </main>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { Collection, DocumentChecked, Files, Search } from "@element-plus/icons-vue";

import { configSummaryApi, type ConfigTodoSummaryResponse } from "@/api/configSummary";
import ConfigTodoSummary from "@/components/ConfigTodoSummary.vue";
import RoleGate from "@/components/RoleGate.vue";
import { useAuthStore } from "@/stores/auth";
import { normalizeApiError, type ApiClientError } from "@/utils/errors";

const auth = useAuthStore();
const summary = ref<ConfigTodoSummaryResponse | null>(null);
const loading = ref(false);
const error = ref<ApiClientError | null>(null);

const cards = [
  {
    title: "模板配置",
    description: "查看模板版本、验证证据和默认版本。",
    to: "/settings/templates",
    icon: Files,
  },
  {
    title: "术语规则集",
    description: "查看 draft 摘要、已发布版本和发布动作。",
    to: "/settings/term-rule-sets",
    icon: Collection,
  },
  {
    title: "术语规则检查",
    description: "浏览当前规则、检查渲染片段并模拟文本命中。",
    to: "/settings/term-rules",
    icon: Search,
  },
  {
    title: "翻译配置",
    description: "管理基础字段 draft、发布和回滚。",
    to: "/settings/translation-profiles",
    icon: DocumentChecked,
  },
];

async function loadSummary(): Promise<void> {
  loading.value = true;
  error.value = null;
  try {
    summary.value = await configSummaryApi.get(auth.user?.role);
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  void loadSummary();
});
</script>

<style scoped lang="scss">
.settings-page {
  display: grid;
  gap: 18px;
}

.page-heading {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  padding: 10px 0 2px;
}

.page-kicker {
  margin: 0 0 4px;
  color: #2563eb;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0;
  text-transform: uppercase;
}

.page-heading h1 {
  margin: 0;
  color: #111827;
  font-size: 28px;
  line-height: 1.2;
}

.page-heading p:last-child {
  margin: 8px 0 0;
  color: #667085;
}

.settings-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
}

.settings-card {
  display: grid;
  grid-template-columns: 42px minmax(0, 1fr);
  gap: 12px;
  min-height: 128px;
  padding: 18px;
  border: 1px solid #d9e2ec;
  border-radius: 8px;
  background: #fff;
  color: #111827;
}

.settings-card:hover {
  border-color: #93c5fd;
  color: #111827;
}

.settings-card-icon {
  display: grid;
  place-items: center;
  width: 42px;
  height: 42px;
  border-radius: 8px;
  background: #eff6ff;
  color: #2563eb;
  font-size: 20px;
}

.settings-card strong,
.settings-card small {
  display: block;
}

.settings-card strong {
  margin-bottom: 8px;
  font-size: 16px;
}

.settings-card small {
  color: #667085;
  font-size: 13px;
  line-height: 1.5;
}

@media (max-width: 820px) {
  .page-heading {
    align-items: flex-start;
    flex-direction: column;
  }

  .settings-grid {
    grid-template-columns: 1fr;
  }
}
</style>
