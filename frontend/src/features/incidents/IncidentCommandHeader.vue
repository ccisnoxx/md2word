<template>
  <WorkbenchPageHeader
    title-id="incident-title"
    kicker="异常分诊"
    title="异常处理"
    description="集中处理失败、阻塞、可重试和长时间未更新的 document_jobs。"
    wide
    section-class="incident-command-header"
  >
    <template #actions>
      <div class="live-pill" :class="{ 'is-loading': loading || backgroundRefreshing }">
        <span aria-hidden="true"></span>
        <strong>{{ syncStatusText }}</strong>
        <small v-if="lastRefreshedAt">{{ formatDateTime(lastRefreshedAt) }}</small>
      </div>
      <el-tooltip content="快捷键 R" placement="bottom">
        <el-button :icon="Refresh" :loading="loading" @click="manualRefresh">刷新</el-button>
      </el-tooltip>
    </template>
  </WorkbenchPageHeader>
</template>

<script setup lang="ts">
import type { UnwrapRef } from "vue";
import { Refresh } from "@element-plus/icons-vue";
import WorkbenchPageHeader from "@/components/WorkbenchPageHeader.vue";
import { formatDateTime } from "@/utils/format";
import type { IncidentQueue } from "./useIncidentQueue";

const { loading, backgroundRefreshing, syncStatusText, lastRefreshedAt, manualRefresh } = defineProps<{
  loading: UnwrapRef<IncidentQueue["loading"]>;
  backgroundRefreshing: UnwrapRef<IncidentQueue["backgroundRefreshing"]>;
  syncStatusText: UnwrapRef<IncidentQueue["syncStatusText"]>;
  lastRefreshedAt: UnwrapRef<IncidentQueue["lastRefreshedAt"]>;
  manualRefresh: () => Promise<void>;
}>();
</script>

<style scoped lang="scss">
.incident-command-header {
  position: relative;
}

.incident-command-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--app-space-4);
}

.command-copy {
  min-width: 0;
}

.command-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--app-space-2);
}

.live-pill {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-height: 32px;
  padding: 6px 10px;
  border: 1px solid var(--app-color-border);
  border-radius: var(--app-radius-md);
  background: var(--app-color-surface);
  color: var(--app-color-text-muted);
}

.live-pill span {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: var(--el-color-success);
}

.live-pill.is-loading span {
  background: var(--el-color-warning);
}

@media (max-width: 900px) {
  .incident-command-header {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>
