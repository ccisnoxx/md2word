<template>
  <section class="retention-table-section app-filter-panel app-table-card app-page-shell app-page-shell--wide" aria-label="过期候选文件">
    <div class="section-header">
      <div>
        <h2 class="section-title">过期候选</h2>
        <p class="section-subtitle">根据 `expires_at` 生成，`deleted` 状态文件不会进入候选；物理删除只执行 selected expired local 文件。</p>
      </div>
      <div class="toolbar">
        <el-tag effect="plain" :type="plan?.deletion_supported ? 'danger' : 'info'">
          deletion_supported={{ String(plan?.deletion_supported ?? false) }}
        </el-tag>
        <el-tag effect="plain">selected={{ selectedFileIds.length }}</el-tag>
        <el-button
          type="warning"
          :icon="Finished"
          :disabled="markableCount === 0"
          :loading="marking"
          @click="markExpired"
        >
          标记 expired
        </el-button>
        <el-button :disabled="selectedFileIds.length === 0" :loading="previewing" @click="previewPhysicalDelete">
          预览物理删除
        </el-button>
        <el-button
          type="danger"
          :disabled="!canOpenDeleteDialog"
          :loading="deleting"
          @click="openPhysicalDeleteDialog"
        >
          执行物理删除
        </el-button>
        <el-button :disabled="selectedFileIds.length === 0" :loading="cleanupPreviewing" @click="previewCleanupRun">
          预览 cleanup run
        </el-button>
        <el-button
          type="danger"
          :disabled="!canOpenCleanupRunDialog"
          :loading="cleanupExecuting"
          @click="openCleanupRunDialog"
        >
          执行 cleanup run
        </el-button>
      </div>
    </div>

    <el-table
      :data="plan?.candidates || []"
      empty-text="暂无过期候选文件"
      class="retention-table"
      table-layout="fixed"
      row-key="file_id"
      @selection-change="handleSelectionChange"
    >
      <el-table-column type="selection" width="48" />
      <el-table-column prop="file_id" label="File ID" min-width="180">
        <template #default="{ row }">
          <span class="mono">{{ row.file_id }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="job_id" label="Job" min-width="170">
        <template #default="{ row }">
          <router-link v-if="row.job_id" :to="`/jobs/${row.job_id}`" class="mono">
            {{ row.job_id }}
          </router-link>
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column prop="file_type" label="Type" min-width="140" />
      <el-table-column prop="storage_provider" label="Storage" min-width="140" />
      <el-table-column prop="status" label="Status" width="110">
        <template #default="{ row }">
          <el-tag size="small" :type="statusTag(row.status)" effect="plain">{{ row.status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="size_bytes" label="Size" width="110">
        <template #default="{ row }">{{ formatBytes(row.size_bytes) }}</template>
      </el-table-column>
      <el-table-column prop="expires_at" label="Expires" min-width="180">
        <template #default="{ row }">{{ formatDateTime(row.expires_at) }}</template>
      </el-table-column>
      <el-table-column prop="object_key" label="Object Key" min-width="320">
        <template #default="{ row }">
          <span class="mono object-key">{{ row.object_key }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="reason" label="Reason" min-width="260" />
    </el-table>
  </section>

</template>

<script setup lang="ts">
// 过期候选文件：标记 expired、物理删除与 cleanup run 的预览入口。
import type { UnwrapRef } from "vue";
import { Finished } from "@element-plus/icons-vue";
import { formatBytes, formatDateTime } from "@/utils/format";
import { statusTag } from "./retentionFormat";
import type { RetentionCleanup } from "./useRetentionCleanup";

const {
  plan,
  selectedFileIds,
  markableCount,
  marking,
  markExpired,
  previewing,
  previewPhysicalDelete,
  canOpenDeleteDialog,
  deleting,
  openPhysicalDeleteDialog,
  cleanupPreviewing,
  previewCleanupRun,
  canOpenCleanupRunDialog,
  cleanupExecuting,
  openCleanupRunDialog,
  handleSelectionChange,
} = defineProps<{
  plan: UnwrapRef<RetentionCleanup["plan"]>;
  selectedFileIds: UnwrapRef<RetentionCleanup["selectedFileIds"]>;
  markableCount: UnwrapRef<RetentionCleanup["markableCount"]>;
  marking: UnwrapRef<RetentionCleanup["marking"]>;
  markExpired: UnwrapRef<RetentionCleanup["markExpired"]>;
  previewing: UnwrapRef<RetentionCleanup["previewing"]>;
  previewPhysicalDelete: UnwrapRef<RetentionCleanup["previewPhysicalDelete"]>;
  canOpenDeleteDialog: UnwrapRef<RetentionCleanup["canOpenDeleteDialog"]>;
  deleting: UnwrapRef<RetentionCleanup["deleting"]>;
  openPhysicalDeleteDialog: UnwrapRef<RetentionCleanup["openPhysicalDeleteDialog"]>;
  cleanupPreviewing: UnwrapRef<RetentionCleanup["cleanupPreviewing"]>;
  previewCleanupRun: UnwrapRef<RetentionCleanup["previewCleanupRun"]>;
  canOpenCleanupRunDialog: UnwrapRef<RetentionCleanup["canOpenCleanupRunDialog"]>;
  cleanupExecuting: UnwrapRef<RetentionCleanup["cleanupExecuting"]>;
  openCleanupRunDialog: UnwrapRef<RetentionCleanup["openCleanupRunDialog"]>;
  handleSelectionChange: UnwrapRef<RetentionCleanup["handleSelectionChange"]>;
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
