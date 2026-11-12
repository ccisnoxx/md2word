<template>
  <section v-if="deleteReport" class="retention-table-section app-filter-panel app-table-card app-page-shell app-page-shell--wide" aria-label="物理删除预览和执行结果">
    <div class="section-header">
      <div>
        <h2 class="section-title">物理删除结果</h2>
        <p class="section-subtitle">
          {{ deleteReport.action_mode }} · generated {{ formatDateTime(deleteReport.generated_at) }} ·
          required confirmation: <span class="mono">{{ deleteReport.confirmation_phrase }}</span>
        </p>
      </div>
      <div class="toolbar">
        <el-tag type="success" effect="plain">deletable={{ totalDeleteValue("deletable") }}</el-tag>
        <el-tag type="danger" effect="plain">deleted={{ totalDeleteValue("deleted") }}</el-tag>
        <el-tag type="warning" effect="plain">skipped={{ totalDeleteValue("skipped") }}</el-tag>
        <el-tag type="danger" effect="plain">failed={{ totalDeleteValue("failed") }}</el-tag>
      </div>
    </div>

    <el-table :data="deleteReport.items" empty-text="暂无物理删除结果" class="retention-table" table-layout="fixed">
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
// 物理删除预览和执行结果。
import type { UnwrapRef } from "vue";
import { formatDateTime } from "@/utils/format";
import { outcomeTag, s3ContractLabel } from "./retentionFormat";
import type { RetentionCleanup } from "./useRetentionCleanup";

const {
  deleteReport,
  totalDeleteValue,
} = defineProps<{
  deleteReport: UnwrapRef<RetentionCleanup["deleteReport"]>;
  totalDeleteValue: UnwrapRef<RetentionCleanup["totalDeleteValue"]>;
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

@media (max-width: 720px) {
  .section-header {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
