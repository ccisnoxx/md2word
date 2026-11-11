<template>
  <section v-loading="libraryLoading" class="retention-table-section app-filter-panel app-table-card app-page-shell app-page-shell--wide" aria-label="文件库搜索">
    <div class="section-header">
      <div>
        <h2 class="section-title">文件库搜索</h2>
        <p class="section-subtitle">只读搜索 document_files 安全摘要；不展示 object_key、bucket、checksum、etag、metadata 或本地路径。</p>
      </div>
      <div class="toolbar">
        <el-tag effect="plain">total={{ librarySearch?.total ?? 0 }}</el-tag>
        <el-tag effect="plain">generated={{ formatDateTime(librarySearch?.generated_at) }}</el-tag>
      </div>
    </div>

    <el-form class="library-filter-form" label-position="top">
      <el-form-item label="搜索">
        <el-input v-model="libraryFilters.q" clearable placeholder="file id / job id / filename / type / status" @keyup.enter="applyLibrarySearch" />
      </el-form-item>
      <el-form-item label="Status">
        <el-select v-model="libraryFilters.status" clearable placeholder="全部状态">
          <el-option label="pending_upload" value="pending_upload" />
          <el-option label="uploaded" value="uploaded" />
          <el-option label="expired" value="expired" />
          <el-option label="deleted" value="deleted" />
        </el-select>
      </el-form-item>
      <el-form-item label="File Type">
        <el-select v-model="libraryFilters.file_type" clearable filterable placeholder="全部类型">
          <el-option v-for="fileType in fileTypeOptions" :key="fileType" :label="fileType" :value="fileType" />
        </el-select>
      </el-form-item>
      <el-form-item label="Storage">
        <el-select v-model="libraryFilters.storage_provider" clearable placeholder="全部存储">
          <el-option label="local_file" value="local_file" />
          <el-option label="local_object" value="local_object" />
          <el-option label="s3" value="s3" />
        </el-select>
      </el-form-item>
      <el-form-item label="Job ID">
        <el-input v-model="libraryFilters.job_id" clearable placeholder="docjob_xxx" @keyup.enter="applyLibrarySearch" />
      </el-form-item>
      <el-form-item label="Sort">
        <el-select v-model="librarySort">
          <el-option label="created desc" value="created_at_desc" />
          <el-option label="created asc" value="created_at_asc" />
          <el-option label="updated desc" value="updated_at_desc" />
          <el-option label="expires desc" value="expires_at_desc" />
          <el-option label="size desc" value="size_bytes_desc" />
          <el-option label="size asc" value="size_bytes_asc" />
        </el-select>
      </el-form-item>
    </el-form>
    <div class="filter-actions">
      <el-button @click="resetLibrarySearch">重置搜索</el-button>
      <el-button type="primary" @click="applyLibrarySearch">搜索</el-button>
    </div>

    <el-table :data="librarySearch?.items || []" empty-text="暂无文件记录" class="retention-table" table-layout="fixed" row-key="file_id">
      <el-table-column prop="file_id" label="File ID" min-width="190">
        <template #default="{ row }"><span class="mono">{{ row.file_id }}</span></template>
      </el-table-column>
      <el-table-column prop="original_filename" label="Filename" min-width="220" show-overflow-tooltip />
      <el-table-column prop="job_id" label="Job" min-width="170">
        <template #default="{ row }">
          <router-link v-if="row.job_id" :to="`/jobs/${row.job_id}`" class="mono">
            {{ row.job_id }}
          </router-link>
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column prop="file_type" label="Type" min-width="150" />
      <el-table-column prop="storage_provider" label="Storage" min-width="130" />
      <el-table-column prop="status" label="Status" width="120">
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
      <el-table-column prop="created_by" label="Created By" min-width="150">
        <template #default="{ row }"><span class="mono">{{ row.created_by || "-" }}</span></template>
      </el-table-column>
      <el-table-column label="Flags" min-width="190">
        <template #default="{ row }">
          <el-tag v-if="row.expired" size="small" type="warning" effect="plain">expired</el-tag>
          <el-tag v-if="row.physical_delete_candidate" size="small" type="danger" effect="plain">delete candidate</el-tag>
          <span v-if="!row.expired && !row.physical_delete_candidate">-</span>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      v-model:current-page="libraryPage"
      v-model:page-size="libraryPageSize"
      :total="librarySearch?.total || 0"
      :page-sizes="[25, 50, 100, 200]"
      layout="sizes, prev, pager, next"
      background
      small
      @current-change="loadFileLibrarySearch"
      @size-change="handleLibraryPageSizeChange"
    />
  </section>

</template>

<script setup lang="ts">
// 文件库搜索区块：筛选表单、只读结果表与分页。
import type { UnwrapRef } from "vue";
import { formatBytes, formatDateTime } from "@/utils/format";
import { fileTypeOptions, statusTag } from "./retentionFormat";
import type { RetentionLibrary } from "./useRetentionLibrary";

const librarySort = defineModel<UnwrapRef<RetentionLibrary["librarySort"]>>("librarySort", { required: true });
const libraryPage = defineModel<UnwrapRef<RetentionLibrary["libraryPage"]>>("libraryPage", { required: true });
const libraryPageSize = defineModel<UnwrapRef<RetentionLibrary["libraryPageSize"]>>("libraryPageSize", { required: true });
const {
  libraryLoading,
  librarySearch,
  libraryFilters,
  applyLibrarySearch,
  resetLibrarySearch,
  loadFileLibrarySearch,
  handleLibraryPageSizeChange,
} = defineProps<{
  libraryLoading: UnwrapRef<RetentionLibrary["libraryLoading"]>;
  librarySearch: UnwrapRef<RetentionLibrary["librarySearch"]>;
  libraryFilters: UnwrapRef<RetentionLibrary["libraryFilters"]>;
  applyLibrarySearch: UnwrapRef<RetentionLibrary["applyLibrarySearch"]>;
  resetLibrarySearch: UnwrapRef<RetentionLibrary["resetLibrarySearch"]>;
  loadFileLibrarySearch: UnwrapRef<RetentionLibrary["loadFileLibrarySearch"]>;
  handleLibraryPageSizeChange: UnwrapRef<RetentionLibrary["handleLibraryPageSizeChange"]>;
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

.library-filter-form {
  display: grid;
  grid-template-columns: 1.8fr repeat(5, minmax(130px, 1fr));
  gap: var(--app-space-3);
}

.filter-actions {
  display: flex;
  justify-content: flex-end;
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

@media (max-width: 920px) {
  .library-filter-form {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .section-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .library-filter-form {
    grid-template-columns: 1fr;
  }
}
</style>
