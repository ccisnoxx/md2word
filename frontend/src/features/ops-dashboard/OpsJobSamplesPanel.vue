<template>
  <section class="job-panels app-page-shell app-page-shell--wide" aria-label="任务样例">
    <el-card class="card-flat job-panel app-panel-card app-table-card" shadow="never">
      <div class="section-header">
        <div>
          <h2 class="section-title">失败任务样例</h2>
          <p class="section-subtitle">最多展示 5 条最近更新的失败任务。</p>
        </div>
        <router-link :to="failedJobsRoute">查看全部失败任务</router-link>
      </div>
      <el-table :data="failedJobs" empty-text="暂无失败任务" table-layout="fixed" class="job-table">
        <el-table-column label="Job" min-width="190">
          <template #default="{ row }">
            <router-link :to="`/jobs/${row.id}`" class="mono">{{ row.id }}</router-link>
          </template>
        </el-table-column>
        <el-table-column label="Stage" min-width="130">
          <template #default="{ row }">{{ stageLabel(row.stage) }}</template>
        </el-table-column>
        <el-table-column label="Updated" min-width="170">
          <template #default="{ row }">{{ formatDateTime(row.updated_at) }}</template>
        </el-table-column>
        <el-table-column label="Error" min-width="280" show-overflow-tooltip>
          <template #default="{ row }">{{ jobErrorSummary(row) }}</template>
        </el-table-column>
        <el-table-column label="Recovery" min-width="260" fixed="right">
          <template #default="{ row }">
            <div class="job-recovery-actions">
              <el-button
                size="small"
                type="warning"
                :icon="RefreshRight"
                :loading="isPreviewingJobAction(row.id, 'retry') || isExecutingJobAction(row.id, 'retry')"
                :disabled="!canRetryDocumentJob(row)"
                :title="documentJobActionDisabledReason(row, 'retry')"
                @click="previewJobRecoveryAction(row, 'retry')"
              >
                重试预览
              </el-button>
              <el-button
                size="small"
                :icon="FolderChecked"
                :loading="isPreviewingJobAction(row.id, 'archive') || isExecutingJobAction(row.id, 'archive')"
                :disabled="!canArchiveDocumentJob(row)"
                :title="documentJobActionDisabledReason(row, 'archive')"
                @click="previewJobRecoveryAction(row, 'archive')"
              >
                归档预览
              </el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card class="card-flat job-panel app-panel-card app-table-card" shadow="never">
      <div class="section-header">
        <div>
          <h2 class="section-title">运行中任务样例</h2>
          <p class="section-subtitle">最多展示 5 条最近更新的运行中任务。</p>
        </div>
        <router-link :to="runningJobsRoute">查看全部运行中任务</router-link>
      </div>
      <el-table :data="runningJobs" empty-text="暂无运行中任务" table-layout="fixed" class="job-table">
        <el-table-column label="Job" min-width="190">
          <template #default="{ row }">
            <router-link :to="`/jobs/${row.id}`" class="mono">{{ row.id }}</router-link>
          </template>
        </el-table-column>
        <el-table-column label="Stage" min-width="130">
          <template #default="{ row }">{{ stageLabel(row.stage) }}</template>
        </el-table-column>
        <el-table-column label="Progress" width="120">
          <template #default="{ row }">{{ row.progress }}%</template>
        </el-table-column>
        <el-table-column label="Updated" min-width="170">
          <template #default="{ row }">{{ formatDateTime(row.updated_at) }}</template>
        </el-table-column>
        <el-table-column label="Recovery" min-width="180" fixed="right">
          <template #default="{ row }">
            <div class="job-recovery-actions">
              <el-button
                size="small"
                type="primary"
                :icon="RefreshRight"
                :loading="isPreviewingJobAction(row.id, 'replay') || isExecutingJobAction(row.id, 'replay')"
                @click="previewJobRecoveryAction(row, 'replay')"
              >
                Replay 预览
              </el-button>
              <el-button
                size="small"
                type="danger"
                :icon="CircleClose"
                :loading="isPreviewingJobAction(row.id, 'cancel') || isExecutingJobAction(row.id, 'cancel')"
                :disabled="!canCancelDocumentJob(row)"
                :title="documentJobActionDisabledReason(row, 'cancel')"
                @click="previewJobRecoveryAction(row, 'cancel')"
              >
                取消预览
              </el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </section>
</template>

<script setup lang="ts">
// 失败/运行中任务样例与恢复动作预览入口。
import type { UnwrapRef } from "vue";
import { formatDateTime, canArchiveDocumentJob, canCancelDocumentJob, canRetryDocumentJob, documentJobActionDisabledReason } from "@/utils/format";
import { CircleClose, FolderChecked, RefreshRight } from "@element-plus/icons-vue";
import { failedJobsRoute, runningJobsRoute, stageLabel, jobErrorSummary } from "./opsDashboardFormat";
import type { OpsDashboardData } from "./useOpsDashboardData";
import type { OpsJobRecovery } from "./useOpsJobRecovery";

const {
  failedJobs,
  isPreviewingJobAction,
  isExecutingJobAction,
  previewJobRecoveryAction,
  runningJobs,
} = defineProps<{
  failedJobs: UnwrapRef<OpsDashboardData["failedJobs"]>;
  isPreviewingJobAction: UnwrapRef<OpsJobRecovery["isPreviewingJobAction"]>;
  isExecutingJobAction: UnwrapRef<OpsJobRecovery["isExecutingJobAction"]>;
  previewJobRecoveryAction: UnwrapRef<OpsJobRecovery["previewJobRecoveryAction"]>;
  runningJobs: UnwrapRef<OpsDashboardData["runningJobs"]>;
}>();
</script>

<style scoped lang="scss">
.job-panels {
  display: grid;
  gap: var(--app-space-4);
}

.job-panels {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.job-panel {
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

.job-table {
  width: 100%;
}

.job-recovery-actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--app-space-2);
}

@media (max-width: 1100px) {
  .job-panels {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .section-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .job-panels {
    grid-template-columns: 1fr;
  }
}
</style>
