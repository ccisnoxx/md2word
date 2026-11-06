<template>
  <el-card class="page-section task-disposition-card card-flat" shadow="never">
    <div class="section-header">
      <div>
        <h2 class="section-title">任务处置</h2>
        <p class="section-subtitle">基于后端任务状态、事件、回调和文件记录汇总；动作可用性以后端返回为准。</p>
      </div>
      <el-button
        :icon="Refresh"
        :loading="loading || eventsLoading || filesLoading || callbackSummaryLoading || translationBatchesLoading"
        @click="loadAll"
      >
        刷新诊断
      </el-button>
    </div>
    <div class="task-disposition-layout">
      <div class="task-disposition-main">
        <el-alert
          class="task-disposition-alert"
          :type="dispositionAlertType"
          :closable="false"
          show-icon
          :title="dispositionTitle"
        >
          <p>{{ dispositionDescription }}</p>
        </el-alert>
        <div class="task-disposition-facts">
          <div v-for="item in dispositionFacts" :key="item.label" class="task-disposition-fact">
            <span>{{ item.label }}</span>
            <strong :class="{ mono: item.mono }">{{ item.value }}</strong>
          </div>
        </div>
      </div>
      <div class="task-action-summary">
        <h3>当前动作</h3>
        <div class="task-action-list">
          <div v-for="action in actionSummaries" :key="action.key" class="task-action-item">
            <el-tag size="small" :type="action.enabled ? 'success' : 'info'" effect="plain">
              {{ action.label }}
              ·
              {{ action.enabled ? "可用" : "不可用" }}
            </el-tag>
            <small v-if="action.reason">{{ action.reason }}</small>
          </div>
        </div>
      </div>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { Refresh } from "@element-plus/icons-vue";
import type { UnwrapRef } from "vue";
import type { JobDetailData } from "./useJobDetailData";
import type { JobDetailDiagnostics } from "./useJobDetailDiagnostics";
const {
  loading,
  eventsLoading,
  filesLoading,
  callbackSummaryLoading,
  translationBatchesLoading,
  loadAll,
  dispositionAlertType,
  dispositionTitle,
  dispositionDescription,
  dispositionFacts,
  actionSummaries,
} = defineProps<{
  loading: UnwrapRef<JobDetailData["loading"]>;
  eventsLoading: UnwrapRef<JobDetailData["eventsLoading"]>;
  filesLoading: UnwrapRef<JobDetailData["filesLoading"]>;
  callbackSummaryLoading: UnwrapRef<JobDetailData["callbackSummaryLoading"]>;
  translationBatchesLoading: UnwrapRef<JobDetailData["translationBatchesLoading"]>;
  loadAll: UnwrapRef<JobDetailData["loadAll"]>;
  dispositionAlertType: UnwrapRef<JobDetailDiagnostics["dispositionAlertType"]>;
  dispositionTitle: UnwrapRef<JobDetailDiagnostics["dispositionTitle"]>;
  dispositionDescription: UnwrapRef<JobDetailDiagnostics["dispositionDescription"]>;
  dispositionFacts: UnwrapRef<JobDetailDiagnostics["dispositionFacts"]>;
  actionSummaries: UnwrapRef<JobDetailDiagnostics["actionSummaries"]>;
}>();
</script>

<style scoped lang="scss">
.task-disposition-card {
  margin-bottom: 12px;
}

.task-disposition-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(240px, 360px);
  gap: 18px;
  align-items: start;
}

.task-disposition-alert p {
  margin: 4px 0 0;
}

.task-disposition-facts {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  margin-top: 14px;
}

.task-disposition-fact {
  min-width: 0;
  padding: 10px;
  border: 1px solid var(--app-color-border);
  border-radius: var(--app-radius-sm);
  background: var(--app-color-surface-muted);
}

.task-disposition-fact span,
.task-action-item small {
  display: block;
  color: var(--app-color-text-muted);
  font-size: 12px;
  line-height: 1.4;
}

.task-disposition-fact strong {
  display: block;
  margin-top: 4px;
  overflow: hidden;
  color: var(--app-color-text);
  font-size: 13px;
  line-height: 1.4;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.task-action-summary h3 {
  margin: 0 0 10px;
  color: var(--app-color-text);
  font-size: 15px;
}

.task-action-list {
  display: grid;
  gap: 8px;
}

.task-action-item {
  display: grid;
  gap: 4px;
}

@media (max-width: 760px) {
  .task-disposition-layout {
    grid-template-columns: 1fr;
  }

  .task-disposition-facts {
    grid-template-columns: 1fr;
  }
}
</style>
