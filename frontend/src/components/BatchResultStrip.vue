<!-- File: frontend/src/components/BatchResultStrip.vue -->
<!-- Purpose: Shared compact batch-operation result strip for high-frequency operation pages. -->
<template>
  <section class="batch-result-strip" aria-label="批量操作结果">
    <div class="batch-result-main">
      <strong>{{ result.title }}</strong>
      <span>
        成功 {{ result.succeeded }} · 失败 {{ result.failed }}
        <template v-if="result.skipped !== null"> · 跳过 {{ result.skipped }}</template>
        · 总计 {{ result.total }}
      </span>
    </div>
    <div class="batch-result-actions">
      <slot name="actions" />
      <el-button size="small" text :disabled="!result.details.length" @click="$emit('update:expanded', !expanded)">
        {{ expanded ? "收起明细" : "展开明细" }}
      </el-button>
      <el-button size="small" text @click="$emit('close')">关闭</el-button>
    </div>
    <ul v-if="expanded && result.details.length" class="batch-result-details">
      <li v-for="detail in result.details" :key="`${detail.id}:${detail.state}:${detail.code}`">
        <span class="mono">{{ detail.id }}</span>
        <span>{{ detail.state === "skipped" ? "已跳过" : "失败" }}</span>
        <span>{{ detail.code || detail.statusCode }}</span>
        <span>{{ detail.detail }}</span>
      </li>
    </ul>
  </section>
</template>

<script setup lang="ts">
import type { NormalizedBatchResult } from "@/utils/batchResults";

defineProps<{
  result: NormalizedBatchResult;
  expanded: boolean;
}>();

defineEmits<{
  "update:expanded": [expanded: boolean];
  close: [];
}>();
</script>

<style scoped lang="scss">
.batch-result-strip {
  display: grid;
  gap: var(--app-space-2);
  padding: 12px;
  border: 1px solid var(--app-color-warning-border);
  border-radius: var(--app-radius-md);
  background: var(--app-color-warning-soft);
}

.batch-result-main,
.batch-result-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--app-space-2);
}

.batch-result-main {
  justify-content: space-between;
}

.batch-result-main strong {
  color: var(--app-color-text);
}

.batch-result-main span {
  color: var(--app-color-text-muted);
  font-size: 13px;
}

.batch-result-actions {
  justify-content: flex-end;
}

.batch-result-details {
  display: grid;
  gap: 6px;
  padding-left: 0;
  margin: 0;
  list-style: none;
}

.batch-result-details li {
  display: grid;
  grid-template-columns: minmax(140px, 1fr) 72px 120px minmax(0, 2fr);
  gap: 8px;
  align-items: center;
  padding: 6px 8px;
  border-radius: var(--app-radius-sm);
  background: var(--app-color-surface);
  color: var(--app-color-text);
  font-size: 13px;
}

@media (max-width: 760px) {
  .batch-result-actions {
    justify-content: flex-start;
  }

  .batch-result-details li {
    grid-template-columns: 1fr;
  }
}
</style>

