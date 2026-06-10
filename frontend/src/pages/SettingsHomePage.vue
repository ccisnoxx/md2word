<!-- frontend/src/pages/SettingsHomePage.vue: Configuration center landing page for V2.1 resources. -->
<template>
  <main class="settings-page" aria-labelledby="settings-title">
    <section class="page-heading">
      <div>
        <p class="page-kicker">Config Management</p>
        <h1 id="settings-title">配置中心</h1>
        <p>按术语、模板和翻译治理链路进入配置资源，并查看发布待办。</p>
      </div>
      <RoleGate>
        <el-tag type="warning" effect="plain">admin 操作已启用</el-tag>
      </RoleGate>
    </section>

    <ConfigTodoSummary :summary="summary" :loading="loading" :error="error" @refresh="loadSummary" />

    <section class="settings-groups" aria-label="配置治理入口">
      <article v-for="group in groups" :key="group.title" class="settings-group">
        <header class="settings-group-header">
          <span class="settings-group-icon" aria-hidden="true">
            <el-icon><component :is="group.icon" /></el-icon>
          </span>
          <span>
            <strong>{{ group.title }}</strong>
            <small>{{ group.description }}</small>
          </span>
        </header>
        <div class="settings-link-list">
          <router-link v-for="entry in group.entries" :key="entry.to" class="settings-link" :to="entry.to">
            <span class="settings-link-icon" aria-hidden="true">
              <el-icon><component :is="entry.icon" /></el-icon>
            </span>
            <span class="settings-link-copy">
              <strong>{{ entry.title }}</strong>
              <small>{{ entry.description }}</small>
            </span>
            <el-tag v-if="entry.badge" size="small" effect="plain">{{ entry.badge }}</el-tag>
          </router-link>
        </div>
      </article>
    </section>
  </main>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { Collection, DocumentChecked, Files, Search, Tickets } from "@element-plus/icons-vue";

import { configSummaryApi, type ConfigTodoSummaryResponse } from "@/api/configSummary";
import ConfigTodoSummary from "@/components/ConfigTodoSummary.vue";
import RoleGate from "@/components/RoleGate.vue";
import { useAuthStore } from "@/stores/auth";
import { normalizeApiError, type ApiClientError } from "@/utils/errors";

const auth = useAuthStore();
const summary = ref<ConfigTodoSummaryResponse | null>(null);
const loading = ref(false);
const error = ref<ApiClientError | null>(null);

const groups = [
  {
    title: "术语工作台",
    description: "区分当前 live 检查与 draft 发布治理，避免绕过版本流程。",
    icon: Collection,
    entries: [
      {
        title: "草稿与发布",
        description: "编辑 draft 规则，查看 diff / preflight，并发布术语规则集。",
        to: "/settings/term-rule-sets",
        icon: Collection,
        badge: "draft",
      },
      {
        title: "当前生效规则",
        description: "只读查看 live runtime store，并模拟术语渲染命中。",
        to: "/settings/term-rules",
        icon: Search,
        badge: "live",
      },
    ],
  },
  {
    title: "模板与版式",
    description: "管理模板文件版本、验证证据和默认模板指针。",
    icon: Files,
    entries: [
      {
        title: "模板配置",
        description: "查看模板版本、创建验证任务，并执行发布 / 设默认。",
        to: "/settings/templates",
        icon: Files,
        badge: "verified",
      },
    ],
  },
  {
    title: "翻译治理",
    description: "维护翻译 profile 与翻译术语集，不承载 prompt 正文或 secret 编辑。",
    icon: DocumentChecked,
    entries: [
      {
        title: "翻译配置",
        description: "管理基础字段 draft、发布、设默认和 rollback。",
        to: "/settings/translation-profiles",
        icon: DocumentChecked,
        badge: "profile",
      },
      {
        title: "翻译术语集",
        description: "通过 CSV draft import/export 管理术语版本和发布。",
        to: "/settings/translation-term-sets",
        icon: Tickets,
        badge: "csv",
      },
    ],
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

.settings-groups {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}

.settings-group {
  display: grid;
  align-content: start;
  gap: 14px;
  min-width: 0;
  padding: 16px;
  border: 1px solid #d9e2ec;
  border-radius: 8px;
  background: #fff;
}

.settings-group-header {
  display: grid;
  grid-template-columns: 42px minmax(0, 1fr);
  gap: 12px;
  align-items: flex-start;
  color: #111827;
}

.settings-group-icon,
.settings-link-icon {
  display: grid;
  place-items: center;
  width: 42px;
  height: 42px;
  border-radius: 8px;
  background: #eff6ff;
  color: #2563eb;
  font-size: 20px;
}

.settings-group-header strong,
.settings-group-header small,
.settings-link-copy strong,
.settings-link-copy small {
  display: block;
}

.settings-group-header strong {
  margin-bottom: 8px;
  font-size: 16px;
}

.settings-group-header small,
.settings-link-copy small {
  color: #667085;
  font-size: 13px;
  line-height: 1.5;
}

.settings-link-list {
  display: grid;
  gap: 8px;
}

.settings-link {
  display: grid;
  grid-template-columns: 34px minmax(0, 1fr) auto;
  gap: 10px;
  align-items: center;
  min-height: 82px;
  padding: 12px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #f8fafc;
  color: #111827;
}

.settings-link:hover {
  border-color: #93c5fd;
  color: #111827;
}

.settings-link-icon {
  width: 34px;
  height: 34px;
  border-radius: 8px;
  font-size: 17px;
}

.settings-link-copy strong {
  margin-bottom: 4px;
  font-size: 14px;
}

@media (max-width: 820px) {
  .page-heading {
    align-items: flex-start;
    flex-direction: column;
  }

  .settings-groups {
    grid-template-columns: 1fr;
  }
}
</style>
