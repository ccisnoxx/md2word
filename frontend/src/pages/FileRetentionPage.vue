<!-- 文件：frontend/src/pages/FileRetentionPage.vue -->
<!-- 用途：admin 文件库、容量策略与受控清理工作区；各区块数据由 features/file-retention 的 composable 持有。 -->
<template>
  <main class="file-retention-page app-page" aria-labelledby="file-retention-title">
    <section class="page-heading app-page-header app-page-shell app-page-shell--wide">
      <div>
        <p class="page-kicker">Files</p>
        <h1 id="file-retention-title" class="page-title">文件管理与清理</h1>
        <p class="page-description">面向内部 admin 的文件库、容量策略和受控清理工作区；系统状态页只保留只读概览。</p>
      </div>
      <div class="heading-actions">
        <el-button :icon="Refresh" :loading="loading || storageLoading || policyLoading || libraryLoading || quotaPolicyLoading || quotaOpsLoading || cleanupHistoryLoading || schedulerDryRunLoading" @click="refreshRetentionPage">刷新</el-button>
      </div>
    </section>

    <ApiErrorAlert class="app-page-shell app-page-shell--wide" :error="error" />

    <section class="file-workspace-nav app-page-shell app-page-shell--wide" aria-label="文件管理工作区导航">
      <button
        v-for="item in fileWorkspaceTabs"
        :key="item.key"
        class="file-workspace-tab app-workspace-tab"
        :class="{ 'is-active': activeFileManagementTab === item.key }"
        type="button"
        @click="selectFileManagementTab(item.key)"
      >
        <span>{{ item.label }}</span>
        <strong>{{ item.value }}</strong>
        <small>{{ item.helper }}</small>
      </button>
    </section>

    <el-tabs v-model="activeFileManagementTab" class="file-management-tabs">
      <el-tab-pane label="文件库" name="library">
        <RetentionLibraryPanel
          v-model:library-sort="librarySort"
          v-model:library-page="libraryPage"
          v-model:library-page-size="libraryPageSize"
          v-bind="{
            libraryLoading, librarySearch, libraryFilters, applyLibrarySearch, resetLibrarySearch,
            loadFileLibrarySearch, handleLibraryPageSizeChange,
          }"
        />
      </el-tab-pane>
      <el-tab-pane label="容量与策略" name="capacity">
        <RetentionStoragePanel
          v-bind="{
            storageLoading, storageUsage, storageQuotaStatus, storageTotalValue, storageReclaimValue,
          }"
        >
          <template #quota>
            <RetentionQuotaPanel
              v-bind="{
                quotaPolicyReport, quotaPolicyLoading, runQuotaPolicyDryRun, quotaPolicyForm,
                quotaPolicySafetyEntries,
              }"
            >
              <template #ops>
                <RetentionQuotaOpsPanel
                  v-bind="{
                    quotaOpsLoading, quotaOpsSummary, loadQuotaPolicyOpsSummary, quotaOpsSafetyEntries,
                  }"
                />
              </template>
            </RetentionQuotaPanel>
          </template>
        </RetentionStoragePanel>
        <RetentionPlanSummary
          v-bind="{
            loading, candidateCount, selectedFileIds, markableCount, plan, totalValue,
          }"
        />
        <RetentionPolicyPanel
          v-bind="{
            policyList, policyLoading, loadPolicies, openCreatePolicyDialog, openEditPolicyDialog,
            previewPolicyImpact, publishPolicy, setDefaultPolicy, disablePolicy, policyImpact,
          }"
        />
      </el-tab-pane>
      <el-tab-pane label="清理执行" name="cleanup">
        <el-alert
          class="retention-notice"
          type="warning"
          title="受控清理"
          :closable="false"
          show-icon
        >
          标记 expired 仍是 metadata-only。物理删除和 manual cleanup run 都必须先预览、选择精确文件、填写 reason 并输入确认短语；scheduler dry-run 只生成只读计划和 lock/history 证据。所有这些操作都不会调用 provider，也不会执行 S3 delete。
            </el-alert>

        <RetentionCandidatesPanel
          v-bind="{
            plan, selectedFileIds, markableCount, marking, markExpired, previewing, previewPhysicalDelete,
            canOpenDeleteDialog, deleting, openPhysicalDeleteDialog, cleanupPreviewing, previewCleanupRun,
            canOpenCleanupRunDialog, cleanupExecuting, openCleanupRunDialog, handleSelectionChange,
          }"
        />
        <RetentionDeleteReportPanel
          v-bind="{
            deleteReport, totalDeleteValue,
          }"
        />
        <RetentionCleanupRunPanel
          v-bind="{
            cleanupRunReport, cleanupTotalValue, cleanupRunSafetyEntries,
          }"
        />
        <RetentionSchedulerPanel
          v-bind="{
            schedulerDryRunReport, schedulerDryRunLoading, runCleanupSchedulerDryRun, schedulerDryRunForm,
            schedulerRetentionCandidateCount, schedulerEstimatedReclaimBytes, schedulerDryRunSafetyEntries,
          }"
        />
        <RetentionHistoryPanel
          v-bind="{
            cleanupRunHistory, cleanupHistoryLoading, loadCleanupRunHistory, inspectCleanupRunHistory,
            selectedCleanupRunHistory, selectedCleanupRunHistorySafetyEntries,
          }"
        />
      </el-tab-pane>
    </el-tabs>

    <RetentionDialogs
      v-bind="{
        deleteDialog, selectedFileIds, deleteReport, canSubmitPhysicalDelete, deleting,
        executePhysicalDelete, cleanupRunDialog, cleanupRunReport, canSubmitCleanupRun,
        cleanupExecuting, executeCleanupRun, policyDialog, policySaving, savePolicy,
      }"
    />
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { Refresh } from "@element-plus/icons-vue";

import ApiErrorAlert from "@/components/ApiErrorAlert.vue";
import RetentionCandidatesPanel from "@/features/file-retention/RetentionCandidatesPanel.vue";
import RetentionCleanupRunPanel from "@/features/file-retention/RetentionCleanupRunPanel.vue";
import RetentionDeleteReportPanel from "@/features/file-retention/RetentionDeleteReportPanel.vue";
import RetentionDialogs from "@/features/file-retention/RetentionDialogs.vue";
import RetentionHistoryPanel from "@/features/file-retention/RetentionHistoryPanel.vue";
import RetentionLibraryPanel from "@/features/file-retention/RetentionLibraryPanel.vue";
import RetentionPlanSummary from "@/features/file-retention/RetentionPlanSummary.vue";
import RetentionPolicyPanel from "@/features/file-retention/RetentionPolicyPanel.vue";
import RetentionQuotaOpsPanel from "@/features/file-retention/RetentionQuotaOpsPanel.vue";
import RetentionQuotaPanel from "@/features/file-retention/RetentionQuotaPanel.vue";
import RetentionSchedulerPanel from "@/features/file-retention/RetentionSchedulerPanel.vue";
import RetentionStoragePanel from "@/features/file-retention/RetentionStoragePanel.vue";
import { useRetentionCapacity } from "@/features/file-retention/useRetentionCapacity";
import { useRetentionCleanup } from "@/features/file-retention/useRetentionCleanup";
import { useRetentionHistory } from "@/features/file-retention/useRetentionHistory";
import { useRetentionLibrary } from "@/features/file-retention/useRetentionLibrary";
import { useRetentionPolicy } from "@/features/file-retention/useRetentionPolicy";
import { formatBytes } from "@/utils/format";
import { type ApiClientError } from "@/utils/errors";

type FileManagementTab = "library" | "capacity" | "cleanup";

const validFileManagementTabs = ["library", "capacity", "cleanup"] as const;
const route = useRoute();
const router = useRouter();
// 页面级错误提示由各区块共享：每个 owner 在请求开始时清空、失败时写入。
const error = ref<ApiClientError | null>(null);
const library = useRetentionLibrary(error);
const capacity = useRetentionCapacity(error);
const policy = useRetentionPolicy(error);
const history = useRetentionHistory(error);
const cleanup = useRetentionCleanup(error, history);
const {
  librarySearch, libraryLoading, libraryFilters, librarySort, libraryPage, libraryPageSize,
  loadFileLibrarySearch, applyLibrarySearch, resetLibrarySearch, handleLibraryPageSizeChange,
} = library;
const {
  storageUsage, storageLoading, quotaPolicyReport, quotaPolicyLoading, quotaPolicyForm, quotaOpsSummary,
  quotaOpsLoading, storageQuotaStatus, quotaPolicySafetyEntries, quotaOpsSafetyEntries, runQuotaPolicyDryRun,
  loadQuotaPolicyOpsSummary, storageTotalValue, storageReclaimValue, loadStorageUsage,
} = capacity;
const {
  policyList, policyImpact, policyLoading, policySaving, policyDialog, loadPolicies, openCreatePolicyDialog,
  openEditPolicyDialog, savePolicy, previewPolicyImpact, publishPolicy, setDefaultPolicy, disablePolicy,
} = policy;
const {
  cleanupRunHistory, selectedCleanupRunHistory, cleanupHistoryLoading, schedulerDryRunReport,
  schedulerDryRunLoading, schedulerDryRunForm, schedulerRetentionCandidateCount,
  schedulerEstimatedReclaimBytes, schedulerDryRunSafetyEntries, selectedCleanupRunHistorySafetyEntries,
  loadCleanupRunHistory, inspectCleanupRunHistory, runCleanupSchedulerDryRun,
} = history;
const {
  plan, loading, marking, deleteReport, cleanupRunReport, previewing, deleting, cleanupPreviewing,
  cleanupExecuting, deleteDialog, cleanupRunDialog, candidateCount, markableCount, selectedFileIds,
  canOpenDeleteDialog, canSubmitPhysicalDelete, canOpenCleanupRunDialog, canSubmitCleanupRun,
  cleanupRunSafetyEntries, markExpired, handleSelectionChange, previewPhysicalDelete, previewCleanupRun,
  openPhysicalDeleteDialog, openCleanupRunDialog, executePhysicalDelete, executeCleanupRun, totalValue,
  totalDeleteValue, cleanupTotalValue, loadPlan,
} = cleanup;
const activeFileManagementTab = ref<FileManagementTab>(readFileManagementTab(route.query.tab));
const fileWorkspaceTabs = computed<Array<{ key: FileManagementTab; label: string; value: string; helper: string }>>(() => [
  {
    key: "library",
    label: "文件库",
    value: String(librarySearch.value?.total ?? "-"),
    helper: "按文件、任务和状态检索",
  },
  {
    key: "capacity",
    label: "容量与策略",
    value: storageQuotaStatus.value,
    helper: `active ${formatBytes(storageTotalValue("active_size_bytes"))} · reclaim ${formatBytes(storageReclaimValue("estimated_reclaimable_size_bytes"))}`,
  },
  {
    key: "cleanup",
    label: "清理执行",
    value: String(candidateCount.value),
    helper: `selected ${selectedFileIds.value.length} · history ${cleanupRunHistory.value?.total ?? 0}`,
  },
]);

// 同步刷新 retention plan、policy governance、storage usage 和 quota ops summary。
function refreshRetentionPage(): void {
  void loadFileLibrarySearch();
  void loadPlan();
  void loadPolicies();
  void loadStorageUsage();
  void loadQuotaPolicyOpsSummary();
  void loadCleanupRunHistory();
}

function selectFileManagementTab(tab: FileManagementTab): void {
  activeFileManagementTab.value = tab;
}

function readFileManagementTab(value: unknown): FileManagementTab {
  const raw = Array.isArray(value) ? value[0] : value;
  return typeof raw === "string" && validFileManagementTabs.includes(raw as FileManagementTab)
    ? raw as FileManagementTab
    : "library";
}

function currentRouteFileManagementTab(): string | null {
  const raw = route.query.tab;
  if (Array.isArray(raw)) {
    return raw[0] || null;
  }
  return typeof raw === "string" ? raw : null;
}

onMounted(() => {
  void loadFileLibrarySearch();
  void loadPlan();
  void loadPolicies();
  void loadStorageUsage();
  void loadQuotaPolicyOpsSummary();
  void loadCleanupRunHistory();
});

watch(
  () => route.query.tab,
  (tab) => {
    const nextTab = readFileManagementTab(tab);
    if (activeFileManagementTab.value !== nextTab) {
      activeFileManagementTab.value = nextTab;
    }
  },
);

watch(activeFileManagementTab, (tab) => {
  if (currentRouteFileManagementTab() === tab) {
    return;
  }
  void router.replace({
    query: {
      ...route.query,
      tab,
    },
  });
});
</script>

<style scoped lang="scss">
.file-retention-page {
  display: grid;
  gap: var(--app-space-4);
}

.page-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--app-space-4);
}

.heading-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--app-space-2);
}

.retention-notice {
  margin-bottom: 0;
}

.file-workspace-nav {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--app-space-3);
}

.file-management-tabs {
  min-width: 0;
}

.file-management-tabs :deep(.el-tabs__content) {
  overflow: visible;
}

.file-management-tabs :deep(.el-tab-pane) {
  display: grid;
  gap: var(--app-space-4);
}

@media (max-width: 920px) {
  .file-workspace-nav {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .page-heading {
    align-items: flex-start;
    flex-direction: column;
  }

  .heading-actions {
    align-items: flex-start;
    flex-direction: column;
  }

  .file-workspace-nav {
    grid-template-columns: 1fr;
  }
}
</style>
