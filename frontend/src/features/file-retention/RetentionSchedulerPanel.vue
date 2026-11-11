<template>
  <section class="retention-table-section scheduler-dry-run-section app-filter-panel app-table-card app-page-shell app-page-shell--wide" aria-label="cleanup scheduler dry-run">
    <div class="section-header">
      <div>
        <h2 class="section-title">Scheduler Dry Run</h2>
        <p class="section-subtitle">手动运行 readonly cleanup runner；只获取并释放 cleanup lock、写入 dry-run history，不启动 scheduler loop，不授权删除。</p>
      </div>
      <div class="toolbar">
        <el-tag v-if="schedulerDryRunReport" effect="plain">run={{ schedulerDryRunReport.run_id }}</el-tag>
        <el-tag v-if="schedulerDryRunReport" effect="plain">generated={{ formatDateTime(schedulerDryRunReport.generated_at) }}</el-tag>
        <el-button type="primary" :icon="Refresh" :loading="schedulerDryRunLoading" @click="runCleanupSchedulerDryRun">
          运行 scheduler dry-run
        </el-button>
      </div>
    </div>

    <el-alert type="info" title="readonly runner" :closable="false" show-icon>
      该按钮不会执行 mark-expired、delete-preview、delete-expired、真实 S3 delete、provider cancellation、alert delivery 或主转换流程；结果不能作为 cleanup execute 授权。
    </el-alert>

    <el-form class="scheduler-dry-run-form" label-position="top">
      <el-form-item label="Owner ID">
        <el-input v-model="schedulerDryRunForm.owner_id" clearable placeholder="留空使用当前 admin user" />
      </el-form-item>
      <el-form-item label="Lock TTL Seconds">
        <el-input-number
          v-model="schedulerDryRunForm.lock_ttl_seconds"
          :min="1"
          :max="900"
          :step="30"
          :precision="0"
          controls-position="right"
        />
      </el-form-item>
    </el-form>

    <div v-if="schedulerDryRunReport" class="scheduler-dry-run-grid app-compact-grid">
      <article class="cleanup-run-card app-compact-card">
        <span>Run</span>
        <strong class="mono object-key">{{ schedulerDryRunReport.run_id }}</strong>
        <small>{{ schedulerDryRunReport.action_mode }}</small>
      </article>
      <article class="cleanup-run-card app-compact-card">
        <span>Candidates</span>
        <strong>{{ schedulerRetentionCandidateCount }}</strong>
        <small>metadata-only retention candidates</small>
      </article>
      <article class="cleanup-run-card app-compact-card">
        <span>Reclaim Estimate</span>
        <strong>{{ formatBytes(schedulerEstimatedReclaimBytes) }}</strong>
        <small>仍需 selected-file delete-preview 验证</small>
      </article>
      <article class="cleanup-run-card app-compact-card">
        <span>Lock</span>
        <strong>{{ schedulerDryRunReport.lock.status }} · released={{ String(schedulerDryRunReport.lock.released) }}</strong>
        <small class="mono object-key">{{ schedulerDryRunReport.lock.owner_id }} · token={{ schedulerDryRunReport.lock.fencing_token }}</small>
      </article>
    </div>

    <div v-if="schedulerDryRunReport" class="safety-grid" aria-label="scheduler dry-run safety flags">
      <el-tag
        v-for="item in schedulerDryRunSafetyEntries"
        :key="item.label"
        :type="item.type"
        effect="plain"
      >
        {{ item.label }}={{ String(item.value) }}
      </el-tag>
    </div>
  </section>

</template>

<script setup lang="ts">
// cleanup scheduler 手动 dry-run：只生成只读报告与 lock/history 证据。
import type { UnwrapRef } from "vue";
import { Refresh } from "@element-plus/icons-vue";
import { formatBytes, formatDateTime } from "@/utils/format";
import type { RetentionHistory } from "./useRetentionHistory";

const {
  schedulerDryRunReport,
  schedulerDryRunLoading,
  runCleanupSchedulerDryRun,
  schedulerDryRunForm,
  schedulerRetentionCandidateCount,
  schedulerEstimatedReclaimBytes,
  schedulerDryRunSafetyEntries,
} = defineProps<{
  schedulerDryRunReport: UnwrapRef<RetentionHistory["schedulerDryRunReport"]>;
  schedulerDryRunLoading: UnwrapRef<RetentionHistory["schedulerDryRunLoading"]>;
  runCleanupSchedulerDryRun: UnwrapRef<RetentionHistory["runCleanupSchedulerDryRun"]>;
  schedulerDryRunForm: UnwrapRef<RetentionHistory["schedulerDryRunForm"]>;
  schedulerRetentionCandidateCount: UnwrapRef<RetentionHistory["schedulerRetentionCandidateCount"]>;
  schedulerEstimatedReclaimBytes: UnwrapRef<RetentionHistory["schedulerEstimatedReclaimBytes"]>;
  schedulerDryRunSafetyEntries: UnwrapRef<RetentionHistory["schedulerDryRunSafetyEntries"]>;
}>();
</script>

<style scoped lang="scss">
.retention-table-section {
  min-width: 0;
}

.section-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--app-space-4);
}

.toolbar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--app-space-2);
}

.scheduler-dry-run-section {
  background: var(--app-color-surface);
}

.scheduler-dry-run-form {
  display: grid;
  grid-template-columns: minmax(220px, 2fr) minmax(180px, 1fr);
  gap: var(--app-space-3);
}

.scheduler-dry-run-grid {
  grid-template-columns: minmax(0, 2fr) repeat(3, minmax(0, 1fr));
}

.cleanup-run-card {
  min-height: 82px;
}

.cleanup-run-card strong {
  font-size: 14px;
}

.safety-grid {
  display: flex;
  flex-wrap: wrap;
  gap: var(--app-space-2);
}

.section-title {
  margin: 0;
}

.section-subtitle {
  margin: var(--app-space-1) 0 0;
}

.mono {
  font-family: var(--app-font-mono);
  font-size: 12px;
}

.object-key {
  overflow-wrap: anywhere;
}

@media (max-width: 920px) {
  .scheduler-dry-run-form,
  .scheduler-dry-run-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .section-header {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
