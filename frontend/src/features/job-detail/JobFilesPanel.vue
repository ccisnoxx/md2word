<template>
  <el-card class="page-section card-flat" shadow="never">
    <div class="section-header">
      <div>
        <h2 class="section-title">文件和结果</h2>
        <p class="section-subtitle">任务绑定文件与生成产物。</p>
      </div>
      <el-button :icon="Refresh" :loading="filesLoading" @click="loadFiles()">刷新文件</el-button>
    </div>
    <ApiErrorAlert :error="filesError" :diagnostic-context="jobErrorDiagnosticContext('document_jobs.files')" />
    <el-table v-loading="filesLoading" :data="files" empty-text="暂无已登记文件" class="job-file-table">
      <el-table-column label="角色" width="128">
        <template #default="{ row }">
          <el-tag size="small" :type="fileTagType(row.file_type)">{{ fileRoleText(row.file_type) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="文件名" min-width="220">
        <template #default="{ row }">
          <div class="file-name">{{ row.original_filename }}</div>
          <div class="file-meta mono">{{ row.id }}</div>
        </template>
      </el-table-column>
      <el-table-column label="类型" min-width="150">
        <template #default="{ row }">{{ fileTypeText(row.file_type) }}</template>
      </el-table-column>
      <el-table-column label="大小" width="110">
        <template #default="{ row }">{{ formatBytes(row.size_bytes) }}</template>
      </el-table-column>
      <el-table-column label="状态" width="116">
        <template #default="{ row }">{{ fileAvailabilityText(row) }}</template>
      </el-table-column>
      <el-table-column label="过期时间" min-width="170">
        <template #default="{ row }">{{ formatDateTime(row.expires_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="108" fixed="right">
        <template #default="{ row }">
          <el-button
            size="small"
            type="primary"
            :icon="Download"
            :disabled="!canDownloadFile(row)"
            :loading="downloadingFileId === row.id"
            @click="handleFileDownload(row)"
          >
            下载
          </el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-card>
</template>

<script setup lang="ts">
import { Download, Refresh } from "@element-plus/icons-vue";
import ApiErrorAlert from "@/components/ApiErrorAlert.vue";
import { formatBytes, formatDateTime } from "@/utils/format";
import { fileRoleText, fileTypeText, fileTagType, canDownloadFile, fileAvailabilityText } from "./jobDetailFormat";
import type { UnwrapRef } from "vue";
import type { JobDetailData } from "./useJobDetailData";
import type { JobDetailActions } from "./useJobDetailActions";
const {
  files,
  filesLoading,
  filesError,
  loadFiles,
  jobErrorDiagnosticContext,
  downloadingFileId,
  handleFileDownload,
} = defineProps<{
  files: UnwrapRef<JobDetailData["files"]>;
  filesLoading: UnwrapRef<JobDetailData["filesLoading"]>;
  filesError: UnwrapRef<JobDetailData["filesError"]>;
  loadFiles: UnwrapRef<JobDetailData["loadFiles"]>;
  jobErrorDiagnosticContext: UnwrapRef<JobDetailData["jobErrorDiagnosticContext"]>;
  downloadingFileId: UnwrapRef<JobDetailActions["downloadingFileId"]>;
  handleFileDownload: UnwrapRef<JobDetailActions["handleFileDownload"]>;
}>();
</script>

<style scoped lang="scss">
.job-file-table {
  width: 100%;
}

.file-name {
  word-break: break-word;
  font-weight: 600;
  color: var(--app-color-text);
}

.file-meta {
  margin-top: 3px;
  color: var(--app-color-text-muted);
  font-size: 12px;
  word-break: break-all;
}
</style>
