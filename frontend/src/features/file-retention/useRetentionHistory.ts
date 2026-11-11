// 清理历史与调度器 owner：cleanup run durable history、单条详情与 scheduler dry-run。
import { computed, reactive, ref, type Ref } from "vue";
import { ElMessage } from "element-plus";

import { filesApi } from "@/api/files";
import type {
  FileRetentionCleanupRunHistoryListResponse,
  FileRetentionCleanupRunHistoryResponse,
  FileRetentionCleanupSchedulerDryRunResponse,
} from "@/api/types";
import { normalizeApiError, type ApiClientError } from "@/utils/errors";
import {
  type StatusTag,
  asRecord,
  numberField,
  schedulerDryRunSafetyTag,
} from "./retentionFormat";

export function useRetentionHistory(
  error: Ref<ApiClientError | null>,
) {
  const cleanupRunHistory = ref<FileRetentionCleanupRunHistoryListResponse | null>(null);
  const selectedCleanupRunHistory = ref<FileRetentionCleanupRunHistoryResponse | null>(null);
  const cleanupHistoryLoading = ref(false);
  const schedulerDryRunReport = ref<FileRetentionCleanupSchedulerDryRunResponse | null>(null);
  const schedulerDryRunLoading = ref(false);

  const schedulerDryRunForm = reactive({
    owner_id: "",
    lock_ttl_seconds: 60,
  });

  const schedulerReadonlyReportRecord = computed(() => asRecord(schedulerDryRunReport.value?.readonly_report));
  const schedulerRetentionRecord = computed(() => asRecord(schedulerReadonlyReportRecord.value?.retention));
  const schedulerStorageUsageRecord = computed(() => asRecord(schedulerReadonlyReportRecord.value?.storage_usage));
  const schedulerRetentionTotals = computed(() => asRecord(schedulerRetentionRecord.value?.totals));
  const schedulerStorageReclaim = computed(() => asRecord(schedulerStorageUsageRecord.value?.reclaim));

  const schedulerRetentionCandidateCount = computed(() => {
    const candidateCountFromTotals = numberField(schedulerRetentionTotals.value, "candidate_files");
    if (candidateCountFromTotals !== null) {
      return candidateCountFromTotals;
    }
    const candidates = schedulerRetentionRecord.value?.candidates;
    return Array.isArray(candidates) ? candidates.length : 0;
  });

  const schedulerEstimatedReclaimBytes = computed(() => (
    numberField(schedulerStorageReclaim.value, "estimated_reclaimable_size_bytes") ?? 0
  ));

  const schedulerDryRunSafetyEntries = computed(() => {
    if (!schedulerDryRunReport.value) {
      return [];
    }
    return Object.entries(schedulerDryRunReport.value.safety).map(([label, value]) => ({
      label,
      value,
      type: schedulerDryRunSafetyTag(label, value),
    })) satisfies Array<{ label: string; value: boolean; type: StatusTag }>;
  });

  const selectedCleanupRunHistorySafetyEntries = computed(() => {
    if (!selectedCleanupRunHistory.value) {
      return [];
    }
    return Object.entries(selectedCleanupRunHistory.value.safety).map(([label, value]) => ({
      label,
      value,
      type: value ? "success" : "info",
    })) satisfies Array<{ label: string; value: boolean; type: StatusTag }>;
  });

  // 读取 cleanup run durable history，不执行任何清理动作。
  async function loadCleanupRunHistory(): Promise<void> {
    cleanupHistoryLoading.value = true;
    error.value = null;
    try {
      cleanupRunHistory.value = await filesApi.listRetentionCleanupRunHistory({ page: 1, page_size: 25 });
    } catch (caught) {
      error.value = normalizeApiError(caught);
    } finally {
      cleanupHistoryLoading.value = false;
    }
  }

  // 读取单条 cleanup run history 详情，便于核对 safety flags。
  async function inspectCleanupRunHistory(runId: string): Promise<void> {
    cleanupHistoryLoading.value = true;
    error.value = null;
    try {
      selectedCleanupRunHistory.value = await filesApi.getRetentionCleanupRunHistory(runId);
    } catch (caught) {
      error.value = normalizeApiError(caught);
    } finally {
      cleanupHistoryLoading.value = false;
    }
  }

  // 手动运行 cleanup scheduler dry-run，只生成 readonly report、lock evidence 和 durable history。
  async function runCleanupSchedulerDryRun(): Promise<void> {
    schedulerDryRunLoading.value = true;
    error.value = null;
    try {
      const response = await filesApi.runRetentionCleanupSchedulerDryRun({
        owner_id: schedulerDryRunForm.owner_id.trim() || null,
        lock_ttl_seconds: schedulerDryRunForm.lock_ttl_seconds,
      });
      schedulerDryRunReport.value = response;
      await loadCleanupRunHistory();
      await showCleanupRunHistory(response.run_id);
      ElMessage.success(`scheduler dry-run 完成：candidates=${schedulerRetentionCandidateCount.value}。`);
    } catch (caught) {
      error.value = normalizeApiError(caught);
    } finally {
      schedulerDryRunLoading.value = false;
    }
  }

  // 供预览/执行流程在拿到 run_id 后展示同一次运行的 durable history；错误交给调用方处理。
  async function showCleanupRunHistory(runId: string): Promise<void> {
    selectedCleanupRunHistory.value = await filesApi.getRetentionCleanupRunHistory(runId);
  }

  return {
    cleanupRunHistory,
    selectedCleanupRunHistory,
    cleanupHistoryLoading,
    schedulerDryRunReport,
    schedulerDryRunLoading,
    schedulerDryRunForm,
    schedulerReadonlyReportRecord,
    schedulerRetentionRecord,
    schedulerStorageUsageRecord,
    schedulerRetentionTotals,
    schedulerStorageReclaim,
    schedulerRetentionCandidateCount,
    schedulerEstimatedReclaimBytes,
    schedulerDryRunSafetyEntries,
    selectedCleanupRunHistorySafetyEntries,
    loadCleanupRunHistory,
    inspectCleanupRunHistory,
    runCleanupSchedulerDryRun,
    showCleanupRunHistory,
  };
}

export type RetentionHistory = ReturnType<typeof useRetentionHistory>;
