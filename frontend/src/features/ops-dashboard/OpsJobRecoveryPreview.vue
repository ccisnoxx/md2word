<template>
  <section v-if="jobRecoveryPreview" class="job-recovery-preview app-page-shell app-page-shell--wide" aria-label="任务恢复预览">
    <el-card class="card-flat dashboard-panel app-panel-card" shadow="never">
      <div class="section-header">
        <div>
          <h2 class="section-title">任务恢复预览</h2>
          <p class="section-subtitle">
            {{ jobRecoveryPreview.action.label }} ·
            <router-link :to="`/jobs/${jobRecoveryPreview.target.target_id}`" class="mono">
              {{ jobRecoveryPreview.target.target_id }}
            </router-link>
          </p>
        </div>
        <div class="toolbar">
          <el-tag :type="jobRecoveryPreview.eligible ? 'success' : 'warning'" effect="plain">
            eligible={{ String(jobRecoveryPreview.eligible) }}
          </el-tag>
          <el-tag effect="plain">status={{ jobRecoveryPreview.target.status || "-" }}</el-tag>
          <el-tag effect="plain">stage={{ jobRecoveryPreview.target.stage || "-" }}</el-tag>
        </div>
      </div>

      <el-alert
        v-if="jobRecoveryPreview.missing_gates.length"
        class="delivery-warning"
        type="warning"
        title="缺少执行 gate"
        :closable="false"
        show-icon
      >
        {{ jobRecoveryPreview.missing_gates.join(" / ") }}
      </el-alert>
      <el-alert
        v-else-if="jobRecoveryPreview.warnings.length"
        class="delivery-warning"
        type="warning"
        title="执行前提醒"
        :closable="false"
        show-icon
      >
        {{ jobRecoveryPreview.warnings.join(" / ") }}
      </el-alert>

      <div class="recovery-preview-grid">
        <article v-for="item in jobRecoveryTargetSummaryItems" :key="item.label" class="recovery-preview-card app-compact-card">
          <span>{{ item.label }}</span>
          <strong>{{ item.value }}</strong>
        </article>
        <article v-for="item in jobRecoveryRiskItems" :key="item.label" class="recovery-preview-card app-compact-card">
          <span>{{ item.label }}</span>
          <strong>{{ booleanLabel(item.value) }}</strong>
        </article>
      </div>

      <div class="recovery-preview-actions">
        <router-link :to="`/jobs/${jobRecoveryPreview.target.target_id}`">打开任务详情</router-link>
        <el-button
          :type="selectedJobRecoveryAction === 'cancel' ? 'danger' : selectedJobRecoveryAction === 'retry' ? 'warning' : 'primary'"
          :icon="selectedJobRecoveryAction === 'cancel' ? CircleClose : selectedJobRecoveryAction === 'archive' ? FolderChecked : RefreshRight"
          :disabled="!canExecutePreviewedJobRecovery"
          :loading="jobRecoveryExecuting"
          @click="executePreviewedJobRecovery"
        >
          执行{{ jobRecoveryActionLabel(selectedJobRecoveryAction) }}
        </el-button>
      </div>
    </el-card>
  </section>
</template>

<script setup lang="ts">
// 任务恢复预览与执行确认。
import type { UnwrapRef } from "vue";
import { CircleClose, FolderChecked, RefreshRight } from "@element-plus/icons-vue";
import { jobRecoveryActionLabel, booleanLabel } from "./opsDashboardFormat";
import type { OpsJobRecovery } from "./useOpsJobRecovery";

const {
  jobRecoveryPreview,
  jobRecoveryTargetSummaryItems,
  jobRecoveryRiskItems,
  selectedJobRecoveryAction,
  canExecutePreviewedJobRecovery,
  jobRecoveryExecuting,
  executePreviewedJobRecovery,
} = defineProps<{
  jobRecoveryPreview: UnwrapRef<OpsJobRecovery["jobRecoveryPreview"]>;
  jobRecoveryTargetSummaryItems: UnwrapRef<OpsJobRecovery["jobRecoveryTargetSummaryItems"]>;
  jobRecoveryRiskItems: UnwrapRef<OpsJobRecovery["jobRecoveryRiskItems"]>;
  selectedJobRecoveryAction: UnwrapRef<OpsJobRecovery["selectedJobRecoveryAction"]>;
  canExecutePreviewedJobRecovery: UnwrapRef<OpsJobRecovery["canExecutePreviewedJobRecovery"]>;
  jobRecoveryExecuting: UnwrapRef<OpsJobRecovery["jobRecoveryExecuting"]>;
  executePreviewedJobRecovery: UnwrapRef<OpsJobRecovery["executePreviewedJobRecovery"]>;
}>();
</script>

<style scoped lang="scss">
.job-recovery-preview {
  display: grid;
  gap: var(--app-space-4);
}

.toolbar {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: var(--app-space-2);
}

.delivery-warning {
  margin-bottom: var(--app-space-4);
}

.dashboard-panel {
  border-color: var(--app-color-border);
}

.section-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--app-space-4);
  margin-bottom: var(--app-space-3);
}

.mono {
  font-family: var(--app-font-mono);
  font-size: 12px;
}

.recovery-preview-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: var(--app-space-3);
}

.recovery-preview-card {
  min-height: 78px;
}

.recovery-preview-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: var(--app-space-3);
}

@media (max-width: 1100px) {
  .recovery-preview-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .section-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .toolbar {
    justify-content: flex-start;
  }

  .recovery-preview-grid {
    grid-template-columns: 1fr;
  }
}
</style>
