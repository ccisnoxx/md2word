<!-- frontend/src/pages/FileRetentionPage.vue: Admin-only metadata retention plan and expired marking page. -->
<template>
  <main class="file-retention-page" aria-labelledby="file-retention-title">
    <section class="page-heading">
      <div>
        <p class="page-kicker">Storage</p>
        <h1 id="file-retention-title">文件保留计划</h1>
        <p>查看已过保留期的 document_files，并仅将 metadata 标记为 expired。</p>
      </div>
      <div class="heading-actions">
        <el-button :icon="Refresh" :loading="loading" @click="loadPlan">刷新</el-button>
        <el-button
          type="warning"
          :icon="Finished"
          :disabled="markableCount === 0"
          :loading="marking"
          @click="markExpired"
        >
          标记 expired
        </el-button>
      </div>
    </section>

    <ApiErrorAlert :error="error" />

    <el-alert
      class="retention-notice"
      type="warning"
      title="metadata-only"
      :closable="false"
      show-icon
    >
      此页面不会删除本地文件、对象存储对象、任务记录或 object_key；只更新过期文件的 metadata 状态。
    </el-alert>

    <section v-loading="loading" class="summary-grid" aria-label="文件保留计划摘要">
      <article class="summary-card">
        <span>候选文件</span>
        <strong>{{ candidateCount }}</strong>
        <small>可标记 uploaded：{{ markableCount }}</small>
      </article>
      <article class="summary-card">
        <span>保留天数</span>
        <strong>{{ plan?.retention_days ?? "-" }}</strong>
        <small>来自后端当前配置</small>
      </article>
      <article class="summary-card">
        <span>文件总数</span>
        <strong>{{ totalValue("files_seen") }}</strong>
        <small>有 expires_at：{{ totalValue("files_with_expires_at") }}</small>
      </article>
      <article class="summary-card">
        <span>生成时间</span>
        <strong class="summary-time">{{ formatDateTime(plan?.generated_at) }}</strong>
        <small>action: {{ plan?.action_mode || "dry_run" }}</small>
      </article>
    </section>

    <section class="retention-table-section" aria-label="过期候选文件">
      <div class="section-header">
        <div>
          <h2 class="section-title">过期候选</h2>
          <p class="section-subtitle">根据 `expires_at` 生成，`deleted` 状态文件不会进入候选。</p>
        </div>
        <el-tag effect="plain" :type="plan?.deletion_supported ? 'danger' : 'info'">
          deletion_supported={{ String(plan?.deletion_supported ?? false) }}
        </el-tag>
      </div>

      <el-table
        :data="plan?.candidates || []"
        empty-text="暂无过期候选文件"
        class="retention-table"
        table-layout="fixed"
      >
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
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { Finished, Refresh } from "@element-plus/icons-vue";

import { filesApi } from "@/api/files";
import type { FileRetentionPlanResponse } from "@/api/types";
import ApiErrorAlert from "@/components/ApiErrorAlert.vue";
import { formatBytes, formatDateTime } from "@/utils/format";
import { normalizeApiError, type ApiClientError } from "@/utils/errors";

type StatusTag = "success" | "warning" | "info" | "danger";

const plan = ref<FileRetentionPlanResponse | null>(null);
const loading = ref(false);
const marking = ref(false);
const error = ref<ApiClientError | null>(null);

const candidateCount = computed(() => plan.value?.candidates.length ?? 0);
const markableCount = computed(() => (
  plan.value?.candidates.filter((candidate) => candidate.status === "uploaded").length ?? 0
));

// 读取当前 retention dry-run 计划。
async function loadPlan(): Promise<void> {
  loading.value = true;
  error.value = null;
  try {
    plan.value = await filesApi.getRetentionPlan();
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    loading.value = false;
  }
}

// 将当前过期候选标记为 expired，但不执行物理删除。
async function markExpired(): Promise<void> {
  if (markableCount.value === 0) {
    return;
  }
  try {
    await ElMessageBox.confirm(
      "该操作只会把当前 uploaded 过期候选的 metadata 状态标记为 expired，不会删除任何文件内容。",
      "标记过期文件",
      {
        confirmButtonText: "标记 expired",
        cancelButtonText: "取消",
        type: "warning",
      },
    );
  } catch {
    return;
  }

  marking.value = true;
  error.value = null;
  try {
    const response = await filesApi.markRetentionExpired();
    plan.value = response;
    ElMessage.success(`已标记 ${response.marked_file_ids.length} 个文件。`);
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    marking.value = false;
  }
}

// 读取 totals 中的数值，缺失时展示 0。
function totalValue(key: string): number {
  return plan.value?.totals[key] ?? 0;
}

// 将 metadata 状态映射为表格标签样式。
function statusTag(status: string): StatusTag {
  if (status === "uploaded") {
    return "warning";
  }
  if (status === "expired") {
    return "info";
  }
  if (status === "deleted") {
    return "danger";
  }
  return "success";
}

onMounted(() => {
  void loadPlan();
});
</script>

<style scoped lang="scss">
.file-retention-page {
  display: grid;
  gap: 18px;
}

.page-heading {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  padding: 10px 0 2px;
}

.page-kicker {
  margin: 0 0 4px;
  color: #2563eb;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0;
  text-transform: uppercase;
}

.page-heading h1 {
  margin: 0;
  color: #111827;
  font-size: 28px;
  line-height: 1.2;
}

.page-heading p:last-child {
  margin: 8px 0 0;
  color: #667085;
}

.heading-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.retention-notice {
  margin-bottom: 0;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.summary-card {
  display: grid;
  gap: 6px;
  min-height: 112px;
  padding: 16px;
  border: 1px solid #d9e2ec;
  border-radius: 8px;
  background: #fff;
}

.summary-card span,
.summary-card strong,
.summary-card small {
  display: block;
}

.summary-card span {
  color: #667085;
  font-size: 13px;
}

.summary-card strong {
  color: #111827;
  font-size: 24px;
  line-height: 1.2;
}

.summary-card small {
  color: #667085;
  font-size: 13px;
  line-height: 1.5;
}

.summary-time {
  font-size: 16px !important;
  line-height: 1.4 !important;
}

.retention-table-section {
  display: grid;
  gap: 12px;
  padding: 16px;
  border: 1px solid #d9e2ec;
  border-radius: 8px;
  background: #fff;
}

.section-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.section-title {
  margin: 0;
  color: #111827;
  font-size: 18px;
}

.section-subtitle {
  margin: 6px 0 0;
  color: #667085;
  font-size: 13px;
}

.retention-table {
  width: 100%;
}

.mono {
  font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace;
  font-size: 12px;
}

.object-key {
  overflow-wrap: anywhere;
}

@media (max-width: 920px) {
  .summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .page-heading,
  .section-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .heading-actions {
    align-items: flex-start;
    flex-direction: column;
  }

  .summary-grid {
    grid-template-columns: 1fr;
  }
}
</style>
