<template>
  <WorkbenchSummaryStrip
    label="优先工作队列"
    :items="workQueueItems"
    wide
    section-class="work-queue-strip"
    @select="(kind: string) => applyWorkQueueFilter(kind as WorkQueueKind)"
  />
</template>

<script setup lang="ts">
import { computed, type UnwrapRef } from "vue";
import type { DocumentJobStatus } from "@/api/types";
import WorkbenchSummaryStrip from "@/components/WorkbenchSummaryStrip.vue";
import type { WorkQueueKind } from "./jobsListQuery";
import type { JobsList } from "./useJobsList";

type WorkQueueItem = {
  id: WorkQueueKind;
  label: string;
  helper: string;
  count: number;
  tone: "danger" | "warning" | "info";
  active: boolean;
};

const {
  filteredSummary,
  staleCount,
  translationQaSummary,
  statusFilter,
  statusGroupFilter,
  sortFilter,
  qaStatusFilter,
  applyWorkQueueFilter,
} = defineProps<{
  filteredSummary: UnwrapRef<JobsList["filteredSummary"]>;
  staleCount: number;
  translationQaSummary: UnwrapRef<JobsList["translationQaSummary"]>;
  statusFilter: UnwrapRef<JobsList["statusFilter"]>;
  statusGroupFilter: UnwrapRef<JobsList["statusGroupFilter"]>;
  sortFilter: UnwrapRef<JobsList["sortFilter"]>;
  qaStatusFilter: UnwrapRef<JobsList["qaStatusFilter"]>;
  applyWorkQueueFilter: JobsList["applyWorkQueueFilter"];
}>();

function countByStatus(status: DocumentJobStatus): number {
  return filteredSummary[status] || 0;
}

const workQueueItems = computed<WorkQueueItem[]>(() => [
  {
    id: "failed",
    label: "失败任务",
    helper: "进入失败处理视图",
    count: countByStatus("failed"),
    tone: "danger",
    active: statusFilter === "failed",
  },
  {
    id: "stale",
    label: "停滞任务",
    helper: "按最久未更新排序",
    count: staleCount,
    tone: "warning",
    active: statusGroupFilter === "active" && sortFilter === "updated_at_asc",
  },
  {
    id: "pending_qa",
    label: "待 QA",
    helper: "翻译复核入口",
    count: translationQaSummary.unreviewed,
    tone: "info",
    active: qaStatusFilter === "unreviewed",
  },
  {
    id: "blocked_qa",
    label: "QA 阻塞",
    helper: "优先解除阻塞",
    count: translationQaSummary.blocked,
    tone: "danger",
    active: qaStatusFilter === "blocked",
  },
]);
</script>

<style scoped lang="scss">
.work-queue-strip {
  position: relative;
  z-index: 1;
}

.work-queue-strip {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--app-space-3);
  margin-top: var(--app-space-3);
}

.work-queue-item {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: var(--app-space-3);
  align-items: center;
  min-width: 0;
  min-height: 74px;
  padding: var(--app-space-3);
  border: 1px solid var(--app-color-border);
  border-radius: var(--app-radius-md);
  background: var(--app-color-surface);
  color: var(--app-color-text);
  text-align: left;
  box-shadow: var(--app-shadow-subtle);
  transition:
    border-color var(--app-motion-fast) ease-out,
    background-color var(--app-motion-fast) ease-out,
    box-shadow var(--app-motion-fast) ease-out;
}

.work-queue-item:hover,
.work-queue-item:focus-visible,
.work-queue-item.is-active {
  border-color: var(--app-color-primary-border);
  background: var(--app-color-primary-soft);
  box-shadow: var(--app-shadow-focus);
  outline: none;
}

.work-queue-item.is-danger {
  border-color: var(--app-color-danger-border);
}

.work-queue-item.is-danger .queue-count {
  color: var(--app-color-danger);
  background: var(--app-color-danger-soft);
}

.work-queue-item.is-warning {
  border-color: var(--app-color-warning-border);
}

.work-queue-item.is-warning .queue-count {
  color: var(--app-color-warning);
  background: var(--app-color-warning-soft);
}

.work-queue-item.is-info .queue-count {
  color: var(--app-color-info);
  background: var(--app-color-info-soft);
}

.queue-count {
  display: inline-grid;
  min-width: 44px;
  height: 44px;
  place-items: center;
  border-radius: var(--app-radius-md);
  font-size: 20px;
  font-weight: 800;
}

.queue-copy {
  display: grid;
  gap: 3px;
  min-width: 0;
}

.queue-copy strong,
.queue-copy small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.queue-copy strong {
  font-size: 14px;
}

.queue-copy small {
  color: var(--app-color-text-muted);
  font-size: 12px;
}

@media (max-width: 1080px) {
  .work-queue-strip {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 760px) {
  .work-queue-strip {
    grid-template-columns: 1fr;
  }
}
</style>
