<template>
  <section class="retention-table-section app-filter-panel app-table-card app-page-shell app-page-shell--wide" aria-label="cleanup run durable history">
    <div class="section-header">
      <div>
        <h2 class="section-title">Cleanup Run History</h2>
        <p class="section-subtitle">持久化 preview/execute 摘要；不展示 object_key、本地路径或文件内容，不启动 scheduler。</p>
      </div>
      <div class="toolbar">
        <el-tag effect="plain">total={{ cleanupRunHistory?.total ?? 0 }}</el-tag>
        <el-button :loading="cleanupHistoryLoading" @click="loadCleanupRunHistory">刷新 history</el-button>
      </div>
    </div>

    <el-table
      v-loading="cleanupHistoryLoading"
      :data="cleanupRunHistory?.items || []"
      empty-text="暂无 cleanup run history"
      class="retention-table"
      table-layout="fixed"
      row-key="run_id"
    >
      <el-table-column prop="run_id" label="Run ID" min-width="190">
        <template #default="{ row }"><span class="mono">{{ row.run_id }}</span></template>
      </el-table-column>
      <el-table-column prop="status" label="Status" width="120">
        <template #default="{ row }">
          <el-tag size="small" :type="cleanupHistoryStatusTag(row.status)" effect="plain">{{ row.status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="action_mode" label="Mode" min-width="150" />
      <el-table-column prop="requested_file_ids" label="Files" width="90">
        <template #default="{ row }">{{ row.requested_file_ids.length }}</template>
      </el-table-column>
      <el-table-column prop="totals" label="Totals" min-width="190">
        <template #default="{ row }">
          <span v-if="row.action_mode === 'scheduler_dry_run'">
            candidates={{ row.totals.candidate_files ?? 0 }} · local={{ row.totals.candidate_local_files ?? 0 }}
          </span>
          <span v-else>
            deleted={{ row.totals.deleted ?? 0 }} · skipped={{ row.totals.skipped ?? 0 }} · failed={{ row.totals.failed ?? 0 }}
          </span>
        </template>
      </el-table-column>
      <el-table-column prop="updated_at" label="Updated" min-width="180">
        <template #default="{ row }">{{ formatDateTime(row.updated_at) }}</template>
      </el-table-column>
      <el-table-column label="Actions" width="100">
        <template #default="{ row }">
          <el-button size="small" @click="inspectCleanupRunHistory(row.run_id)">查看</el-button>
        </template>
      </el-table-column>
    </el-table>

    <div v-if="selectedCleanupRunHistory" class="cleanup-history-detail app-compact-grid">
      <article class="cleanup-run-card app-compact-card">
        <span>Preview Hash</span>
        <strong class="mono object-key">{{ selectedCleanupRunHistory.preview_hash }}</strong>
        <small>run <span class="mono">{{ selectedCleanupRunHistory.run_id }}</span></small>
      </article>
      <article class="cleanup-run-card app-compact-card">
        <span>Reason</span>
        <strong>{{ selectedCleanupRunHistory.reason || "-" }}</strong>
        <small>{{ selectedCleanupRunHistory.error_code || selectedCleanupRunHistory.action_mode }}</small>
      </article>
      <article class="cleanup-run-card app-compact-card">
        <span>Requested Files</span>
        <strong>{{ selectedCleanupRunHistory.requested_file_ids.length }}</strong>
        <small class="mono object-key">{{ selectedCleanupRunHistory.requested_file_ids.join(", ") }}</small>
      </article>
      <article class="cleanup-run-card app-compact-card">
        <span>Signed Plan</span>
        <strong class="mono object-key">{{ selectedCleanupRunHistory.cleanup_plan?.plan_id || "-" }}</strong>
        <small>expires {{ formatDateTime(selectedCleanupRunHistory.cleanup_plan?.expires_at) }}</small>
      </article>
    </div>

    <div v-if="selectedCleanupRunHistory" class="safety-grid" aria-label="cleanup run history safety flags">
      <el-tag
        v-for="item in selectedCleanupRunHistorySafetyEntries"
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
// cleanup run durable history 与单条详情。
import type { UnwrapRef } from "vue";
import { formatDateTime } from "@/utils/format";
import { cleanupHistoryStatusTag } from "./retentionFormat";
import type { RetentionHistory } from "./useRetentionHistory";

const {
  cleanupRunHistory,
  cleanupHistoryLoading,
  loadCleanupRunHistory,
  inspectCleanupRunHistory,
  selectedCleanupRunHistory,
  selectedCleanupRunHistorySafetyEntries,
} = defineProps<{
  cleanupRunHistory: UnwrapRef<RetentionHistory["cleanupRunHistory"]>;
  cleanupHistoryLoading: UnwrapRef<RetentionHistory["cleanupHistoryLoading"]>;
  loadCleanupRunHistory: UnwrapRef<RetentionHistory["loadCleanupRunHistory"]>;
  inspectCleanupRunHistory: UnwrapRef<RetentionHistory["inspectCleanupRunHistory"]>;
  selectedCleanupRunHistory: UnwrapRef<RetentionHistory["selectedCleanupRunHistory"]>;
  selectedCleanupRunHistorySafetyEntries: UnwrapRef<RetentionHistory["selectedCleanupRunHistorySafetyEntries"]>;
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

.cleanup-history-detail {
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

.retention-table {
  width: 100%;
}

.mono {
  font-family: var(--app-font-mono);
  font-size: 12px;
}

.object-key {
  overflow-wrap: anywhere;
}

@media (max-width: 920px) {
  .cleanup-history-detail {
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
