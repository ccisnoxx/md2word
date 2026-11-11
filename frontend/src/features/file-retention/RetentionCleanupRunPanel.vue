<template>
  <section v-if="cleanupRunReport" class="retention-table-section app-filter-panel app-table-card app-page-shell app-page-shell--wide" aria-label="cleanup run 预览和执行结果">
    <div class="section-header">
      <div>
        <h2 class="section-title">Cleanup Run 结果</h2>
        <p class="section-subtitle">
          {{ cleanupRunReport.action_mode }} · run <span class="mono">{{ cleanupRunReport.run_id }}</span> ·
          generated {{ formatDateTime(cleanupRunReport.generated_at) }} · max_files={{ cleanupRunReport.max_files }}
        </p>
      </div>
      <div class="toolbar">
        <el-tag type="success" effect="plain">deletable={{ cleanupTotalValue("deletable") }}</el-tag>
        <el-tag type="danger" effect="plain">deleted={{ cleanupTotalValue("deleted") }}</el-tag>
        <el-tag type="warning" effect="plain">skipped={{ cleanupTotalValue("skipped") }}</el-tag>
        <el-tag type="danger" effect="plain">failed={{ cleanupTotalValue("failed") }}</el-tag>
      </div>
    </div>

    <div class="cleanup-run-grid app-compact-grid">
      <article class="cleanup-run-card app-compact-card">
        <span>Preview Hash</span>
        <strong class="mono object-key">{{ cleanupRunReport.preview_hash }}</strong>
        <small>execute 必须提交同一个 hash；状态变化后需要重新 preview。</small>
      </article>
      <article class="cleanup-run-card app-compact-card">
        <span>Requested Files</span>
        <strong>{{ cleanupRunReport.requested_file_ids.length }}</strong>
        <small class="mono object-key">{{ cleanupRunReport.requested_file_ids.join(", ") }}</small>
      </article>
      <article class="cleanup-run-card app-compact-card">
        <span>Physical Delete</span>
        <strong>{{ cleanupRunReport.physical_delete.action_mode }}</strong>
        <small>复用 selected-file physical-delete safety contract。</small>
      </article>
      <article class="cleanup-run-card app-compact-card">
        <span>Signed Plan</span>
        <strong class="mono object-key">{{ cleanupRunReport.cleanup_plan?.plan_id || "-" }}</strong>
        <small>expires {{ formatDateTime(cleanupRunReport.cleanup_plan?.expires_at) }} · {{ cleanupRunReport.cleanup_plan?.signature_algorithm || "-" }}</small>
      </article>
    </div>

    <div class="safety-grid" aria-label="cleanup run safety flags">
      <el-tag
        v-for="item in cleanupRunSafetyEntries"
        :key="item.label"
        :type="item.type"
        effect="plain"
      >
        {{ item.label }}={{ String(item.value) }}
      </el-tag>
    </div>

    <el-table :data="cleanupRunReport.physical_delete.items" empty-text="暂无 cleanup run 结果" class="retention-table" table-layout="fixed">
      <el-table-column prop="file_id" label="File ID" min-width="180">
        <template #default="{ row }">
          <span class="mono">{{ row.file_id }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="outcome" label="Outcome" min-width="180">
        <template #default="{ row }">
          <el-tag size="small" :type="outcomeTag(row.outcome)" effect="plain">{{ row.outcome }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="status_before" label="Before" width="110">
        <template #default="{ row }">{{ row.status_before || "-" }}</template>
      </el-table-column>
      <el-table-column prop="status_after" label="After" width="110">
        <template #default="{ row }">{{ row.status_after || "-" }}</template>
      </el-table-column>
      <el-table-column prop="storage_provider" label="Storage" min-width="130">
        <template #default="{ row }">{{ row.storage_provider || "-" }}</template>
      </el-table-column>
      <el-table-column prop="s3_delete_contract" label="S3 Contract" min-width="190">
        <template #default="{ row }">
          <el-tag
            v-if="row.s3_delete_contract"
            size="small"
            :type="row.s3_delete_contract.target_exact ? 'warning' : 'danger'"
            effect="plain"
          >
            {{ s3ContractLabel(row) }}
          </el-tag>
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column prop="deleted" label="Deleted" width="100">
        <template #default="{ row }">{{ row.deleted ? "yes" : "no" }}</template>
      </el-table-column>
      <el-table-column prop="metadata_updated" label="Metadata" width="110">
        <template #default="{ row }">{{ row.metadata_updated ? "updated" : "unchanged" }}</template>
      </el-table-column>
      <el-table-column prop="reason" label="Reason" min-width="280" show-overflow-tooltip />
      <el-table-column prop="object_key" label="Object Key" min-width="320">
        <template #default="{ row }">
          <span class="mono object-key">{{ row.object_key || "-" }}</span>
        </template>
      </el-table-column>
    </el-table>
  </section>

</template>

<script setup lang="ts">
// manual cleanup run 预览和执行结果。
import type { UnwrapRef } from "vue";
import { formatDateTime } from "@/utils/format";
import { outcomeTag, s3ContractLabel } from "./retentionFormat";
import type { RetentionCleanup } from "./useRetentionCleanup";

const {
  cleanupRunReport,
  cleanupTotalValue,
  cleanupRunSafetyEntries,
} = defineProps<{
  cleanupRunReport: UnwrapRef<RetentionCleanup["cleanupRunReport"]>;
  cleanupTotalValue: UnwrapRef<RetentionCleanup["cleanupTotalValue"]>;
  cleanupRunSafetyEntries: UnwrapRef<RetentionCleanup["cleanupRunSafetyEntries"]>;
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

.cleanup-run-grid {
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
  .cleanup-run-grid {
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
