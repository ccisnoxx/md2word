<template>
  <section v-loading="loading" class="summary-grid app-metric-grid app-page-shell app-page-shell--wide" aria-label="文件清理计划摘要">
    <article class="summary-card app-metric-card">
      <span>候选文件</span>
      <strong>{{ candidateCount }}</strong>
      <small>已选择：{{ selectedFileIds.length }} · 可标记 uploaded：{{ markableCount }}</small>
    </article>
    <article class="summary-card app-metric-card">
      <span>保留天数</span>
      <strong>{{ plan?.retention_days ?? "-" }}</strong>
      <small>来自后端当前配置</small>
    </article>
    <article class="summary-card app-metric-card">
      <span>文件总数</span>
      <strong>{{ totalValue("files_seen") }}</strong>
      <small>有 expires_at：{{ totalValue("files_with_expires_at") }}</small>
    </article>
    <article class="summary-card app-metric-card">
      <span>生成时间</span>
      <strong class="summary-time">{{ formatDateTime(plan?.generated_at) }}</strong>
      <small>action: {{ plan?.action_mode || "dry_run" }}</small>
    </article>
  </section>
</template>

<script setup lang="ts">
// 文件清理计划摘要指标。
import type { UnwrapRef } from "vue";
import { formatDateTime } from "@/utils/format";
import type { RetentionCleanup } from "./useRetentionCleanup";

const {
  loading,
  candidateCount,
  selectedFileIds,
  markableCount,
  plan,
  totalValue,
} = defineProps<{
  loading: UnwrapRef<RetentionCleanup["loading"]>;
  candidateCount: UnwrapRef<RetentionCleanup["candidateCount"]>;
  selectedFileIds: UnwrapRef<RetentionCleanup["selectedFileIds"]>;
  markableCount: UnwrapRef<RetentionCleanup["markableCount"]>;
  plan: UnwrapRef<RetentionCleanup["plan"]>;
  totalValue: UnwrapRef<RetentionCleanup["totalValue"]>;
}>();
</script>

<style scoped lang="scss">
.summary-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.summary-time {
  font-size: 16px !important;
  line-height: 1.4 !important;
}

@media (max-width: 920px) {
  .summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .summary-grid {
    grid-template-columns: 1fr;
  }
}
</style>
