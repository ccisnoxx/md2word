<!-- frontend/src/components/JobStatusBadge.vue: Text badge for document job status. -->
<template>
  <el-tag class="job-status-badge" :class="statusClass" :type="tagType" effect="plain" round>{{ text }}</el-tag>
</template>

<script setup lang="ts">
import { computed } from "vue";

import type { DocumentJobStatus } from "@/api/types";
import { jobStatusText } from "@/utils/format";

const props = defineProps<{
  status: DocumentJobStatus | string;
}>();

const text = computed(() => jobStatusText[props.status as DocumentJobStatus] || props.status);
const statusClass = computed(() => `is-${String(props.status)}`);
const tagType = computed(() => {
  switch (props.status) {
    case "succeeded":
      return "success";
    case "failed":
      return "danger";
    case "running":
      return "warning";
    case "canceled":
      return "info";
    default:
      return "primary";
  }
});
</script>

<style scoped lang="scss">
.job-status-badge {
  min-width: 68px;
  justify-content: center;
  border-radius: var(--app-radius-pill);
  font-weight: 650;
}

.job-status-badge.is-succeeded {
  border-color: var(--app-color-success-border);
  background: var(--app-color-success-soft);
  color: var(--app-color-success);
}

.job-status-badge.is-failed {
  border-color: var(--app-color-danger-border);
  background: var(--app-color-danger-soft);
  color: var(--app-color-danger);
}

.job-status-badge.is-running,
.job-status-badge.is-pending,
.job-status-badge.is-queued {
  border-color: var(--app-color-warning-border);
  background: var(--app-color-warning-soft);
  color: var(--app-color-warning);
}

.job-status-badge.is-canceled {
  border-color: var(--app-color-border);
  background: var(--app-color-surface-muted);
  color: var(--app-color-text-muted);
}
</style>
