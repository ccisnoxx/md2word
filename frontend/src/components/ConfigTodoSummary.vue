<!-- frontend/src/components/ConfigTodoSummary.vue: Render configuration-release todo counters. -->
<template>
  <el-card class="config-todo card-flat" shadow="never">
    <div class="section-header">
      <div>
        <h2 class="section-title">配置发布待办</h2>
        <p class="section-subtitle">只统计模板、术语规则和翻译配置发布相关事项。</p>
      </div>
      <el-button :icon="Refresh" :loading="loading" @click="$emit('refresh')">刷新</el-button>
    </div>

    <ApiErrorAlert :error="error" />

    <el-skeleton v-if="loading" :rows="2" animated />
    <el-empty v-else-if="items.length === 0" description="暂无配置发布待办" :image-size="80" />
    <div v-else class="todo-grid">
      <article v-for="item in items" :key="item.key" class="todo-item">
        <span class="todo-label">{{ item.label }}</span>
        <strong>{{ item.value }}</strong>
        <small>{{ item.helper }}</small>
      </article>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { Refresh } from "@element-plus/icons-vue";

import type { ConfigTodoSummaryResponse } from "@/api/configSummary";
import ApiErrorAlert from "@/components/ApiErrorAlert.vue";
import type { ApiClientError } from "@/utils/errors";

const props = defineProps<{
  summary: ConfigTodoSummaryResponse | null;
  loading: boolean;
  error: ApiClientError | null;
}>();

defineEmits<{
  refresh: [];
}>();

const items = computed(() => {
  const summary = props.summary;
  if (!summary) {
    return [];
  }

  const nextItems: Array<{ key: string; label: string; value: string | number; helper: string }> = [];
  if (summary.pendingReviewProposals !== null) {
    nextItems.push({
      key: "pending-proposals",
      label: "待审核术语建议",
      value: summary.pendingReviewProposals,
      helper: "admin 审核队列",
    });
  }
  if (summary.approvedProposals !== null) {
    nextItems.push({
      key: "approved-proposals",
      label: "已通过待发布建议",
      value: summary.approvedProposals,
      helper: "需随规则集发布",
    });
  }
  nextItems.push({
    key: "template-drafts",
    label: "模板 draft 版本",
    value: summary.templateDraftVersions,
    helper: `${summary.unverifiedTemplateDraftVersions} 个缺少验证证据`,
  });
  nextItems.push({
    key: "translation-drafts",
    label: "翻译配置 draft",
    value: summary.translationProfilesUnavailable ? "不可用" : summary.translationDraftProfiles ?? 0,
    helper: summary.translationProfilesUnavailable ? "当前部署未启用 MySQL resource service" : "存在未发布草稿",
  });
  return nextItems.filter((item) => item.value === "不可用" || Number(item.value) > 0);
});
</script>

<style scoped lang="scss">
.config-todo {
  border: 1px solid #d9e2ec;
}

.todo-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.todo-item {
  display: grid;
  gap: 6px;
  min-height: 104px;
  padding: 14px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fff;
}

.todo-label {
  color: #475467;
  font-size: 13px;
}

.todo-item strong {
  color: #111827;
  font-size: 28px;
  line-height: 1;
}

.todo-item small {
  color: #667085;
  font-size: 12px;
}

@media (max-width: 960px) {
  .todo-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .todo-grid {
    grid-template-columns: 1fr;
  }
}
</style>
