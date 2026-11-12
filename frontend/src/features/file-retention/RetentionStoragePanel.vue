<template>
  <section v-loading="storageLoading" class="retention-table-section app-filter-panel app-table-card app-page-shell app-page-shell--wide" aria-label="存储使用和容量 readiness">
    <div class="section-header">
      <div>
        <h2 class="section-title">存储使用与容量 readiness</h2>
        <p class="section-subtitle">只基于 document_files metadata 估算；不验证对象存在性，不自动选择文件，不执行删除。</p>
      </div>
      <div class="toolbar">
        <el-tag effect="plain">basis={{ storageUsage?.reclaim.estimation_basis || "metadata_only" }}</el-tag>
        <el-tag effect="plain" :type="storageQuotaStatusTag(storageQuotaStatus)">quota={{ storageQuotaStatus }}</el-tag>
        <el-tag effect="plain">generated={{ formatDateTime(storageUsage?.generated_at) }}</el-tag>
      </div>
    </div>

    <div class="summary-grid app-metric-grid">
      <article class="summary-card app-metric-card">
        <span>Active Used</span>
        <strong>{{ formatBytes(storageTotalValue("active_size_bytes")) }}</strong>
        <small>active files: {{ storageTotalValue("active_files") }} / seen: {{ storageTotalValue("files_seen") }}</small>
      </article>
      <article class="summary-card app-metric-card">
        <span>Expired Estimate</span>
        <strong>{{ formatBytes(storageTotalValue("expired_size_bytes")) }}</strong>
        <small>expired files: {{ storageTotalValue("expired_files") }}</small>
      </article>
      <article class="summary-card app-metric-card">
        <span>Reclaim Estimate</span>
        <strong>{{ formatBytes(storageReclaimValue("estimated_reclaimable_size_bytes")) }}</strong>
        <small>estimated files: {{ storageReclaimValue("estimated_reclaimable_files") }} · 仍需 delete-preview 验证</small>
      </article>
      <article class="summary-card app-metric-card">
        <span>Disk Free</span>
        <strong>{{ formatBytes(storageUsage?.artifact_disk_free_bytes ?? null) }}</strong>
        <small>{{ storageUsage?.artifact_storage || "-" }} · writable={{ String(storageUsage?.artifact_root_writable ?? "-") }}</small>
      </article>
    </div>

  <slot name="quota" />
    <div class="storage-group-grid">
      <article class="storage-group-card app-evidence-panel app-table-card" aria-label="按 storage provider 汇总">
        <h3>By Provider</h3>
        <el-table :data="storageUsage?.by_storage_provider || []" empty-text="暂无 provider 汇总" table-layout="fixed">
          <el-table-column prop="key" label="Provider" min-width="130" />
          <el-table-column prop="file_count" label="Files" width="80" />
          <el-table-column prop="size_bytes" label="Size" min-width="110">
            <template #default="{ row }">{{ formatBytes(row.size_bytes) }}</template>
          </el-table-column>
          <el-table-column prop="expired_size_bytes" label="Expired" min-width="110">
            <template #default="{ row }">{{ formatBytes(row.expired_size_bytes) }}</template>
          </el-table-column>
          <el-table-column prop="estimated_reclaimable_size_bytes" label="Reclaim" min-width="110">
            <template #default="{ row }">{{ formatBytes(row.estimated_reclaimable_size_bytes) }}</template>
          </el-table-column>
        </el-table>
      </article>

      <article class="storage-group-card app-evidence-panel app-table-card" aria-label="按 file type 汇总">
        <h3>By File Type</h3>
        <el-table :data="storageUsage?.by_file_type || []" empty-text="暂无 file type 汇总" table-layout="fixed">
          <el-table-column prop="key" label="Type" min-width="150" />
          <el-table-column prop="file_count" label="Files" width="80" />
          <el-table-column prop="size_bytes" label="Size" min-width="110">
            <template #default="{ row }">{{ formatBytes(row.size_bytes) }}</template>
          </el-table-column>
          <el-table-column prop="expired_count" label="Expired" width="90" />
          <el-table-column prop="estimated_reclaimable_count" label="Reclaim" width="90" />
        </el-table>
      </article>

      <article class="storage-group-card app-evidence-panel app-table-card" aria-label="按 status 汇总">
        <h3>By Status</h3>
        <el-table :data="storageUsage?.by_status || []" empty-text="暂无 status 汇总" table-layout="fixed">
          <el-table-column prop="key" label="Status" min-width="120" />
          <el-table-column prop="file_count" label="Files" width="80" />
          <el-table-column prop="size_bytes" label="Size" min-width="110">
            <template #default="{ row }">{{ formatBytes(row.size_bytes) }}</template>
          </el-table-column>
          <el-table-column prop="expired_size_bytes" label="Expired" min-width="110">
            <template #default="{ row }">{{ formatBytes(row.expired_size_bytes) }}</template>
          </el-table-column>
          <el-table-column prop="estimated_reclaimable_size_bytes" label="Reclaim" min-width="110">
            <template #default="{ row }">{{ formatBytes(row.estimated_reclaimable_size_bytes) }}</template>
          </el-table-column>
        </el-table>
      </article>
    </div>
  </section>

</template>

<script setup lang="ts">
// 存储使用与容量 readiness 区块；配额面板通过 quota 插槽放入。
import type { UnwrapRef } from "vue";
import { formatBytes, formatDateTime } from "@/utils/format";
import { storageQuotaStatusTag } from "./retentionFormat";
import type { RetentionCapacity } from "./useRetentionCapacity";

const {
  storageLoading,
  storageUsage,
  storageQuotaStatus,
  storageTotalValue,
  storageReclaimValue,
} = defineProps<{
  storageLoading: UnwrapRef<RetentionCapacity["storageLoading"]>;
  storageUsage: UnwrapRef<RetentionCapacity["storageUsage"]>;
  storageQuotaStatus: UnwrapRef<RetentionCapacity["storageQuotaStatus"]>;
  storageTotalValue: UnwrapRef<RetentionCapacity["storageTotalValue"]>;
  storageReclaimValue: UnwrapRef<RetentionCapacity["storageReclaimValue"]>;
}>();
</script>

<style scoped lang="scss">
.summary-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

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

.storage-group-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--app-space-3);
}

.storage-group-card {
  min-width: 0;
}

.storage-group-card h3 {
  margin: 0;
  color: var(--app-color-text);
  font-size: 14px;
}

.section-title {
  margin: 0;
}

.section-subtitle {
  margin: var(--app-space-1) 0 0;
}

@media (max-width: 920px) {
  .summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .storage-group-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .section-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .summary-grid {
    grid-template-columns: 1fr;
  }
}
</style>
