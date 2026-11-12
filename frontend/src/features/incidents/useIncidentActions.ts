// 异常处置动作 owner：单条重试、批量重试/刷新、批量结果与失败项重选；列表与诊断刷新委托给各自 owner。
import { computed, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";

import { documentJobIncidentsApi } from "@/api/documentJobIncidents";
import { documentJobsApi } from "@/api/documentJobs";
import type { DocumentJobIncidentBulkResponse, DocumentJobIncidentQueueItemResponse } from "@/api/types";
import { normalizeIncidentBatchResult } from "@/utils/batchResults";
import { normalizeApiError } from "@/utils/errors";
import { countBatchRetryable, failedOrSkippedBatchItems } from "@/utils/incidents";
import type { IncidentDiagnostic } from "./useIncidentDiagnostic";
import type { IncidentQueue } from "./useIncidentQueue";

export function useIncidentActions(
  queue: Pick<IncidentQueue, "error" | "items" | "selectedItems" | "loadIncidents">,
  diagnostic: Pick<IncidentDiagnostic, "selectedIncidentJobId" | "loadDiagnostics">,
  table: {
    clearSelection: () => void;
    toggleRowSelection: (item: DocumentJobIncidentQueueItemResponse, selected: boolean) => void;
  },
) {
  const { error, items, selectedItems, loadIncidents } = queue;
  const batchLoading = ref(false);
  const batchResult = ref<DocumentJobIncidentBulkResponse | null>(null);
  const batchResultExpanded = ref(false);
  const actionPending = ref<Record<string, "retry" | undefined>>({});

  const selectedRetryableCount = computed(() => countBatchRetryable(selectedItems.value).retryable);
  const selectedNonRetryableCount = computed(() => countBatchRetryable(selectedItems.value).nonRetryable);
  const failedBatchItems = computed(() => failedOrSkippedBatchItems(batchResult.value));
  const batchResultActionLabel = computed(() => {
    if (!batchResult.value) {
      return "";
    }
    return batchResult.value.action === "retry" ? "批量重试" : "批量刷新";
  });
  const normalizedBatchResult = computed(() =>
    batchResult.value ? normalizeIncidentBatchResult(batchResultActionLabel.value, batchResult.value) : null,
  );

  function clearBatchResult(): void {
    batchResult.value = null;
  }

  function isActionBusy(jobId: string): boolean {
    return Boolean(actionPending.value[jobId]);
  }

  function setActionPending(jobId: string, action: "retry"): void {
    actionPending.value = { ...actionPending.value, [jobId]: action };
  }

  function clearActionPending(jobId: string): void {
    const next = { ...actionPending.value };
    delete next[jobId];
    actionPending.value = next;
  }

  async function handleSingleRetry(item: DocumentJobIncidentQueueItemResponse): Promise<void> {
    if (!item.retryable || isActionBusy(item.job.id)) {
      return;
    }
    setActionPending(item.job.id, "retry");
    error.value = null;
    try {
      await documentJobsApi.retry(item.job.id, { reason: "incident triage retry" });
      ElMessage.success("任务已提交重试。");
      await loadIncidents({ preserveError: true });
      if (diagnostic.selectedIncidentJobId.value === item.job.id) {
        await diagnostic.loadDiagnostics(item.job.id);
      }
    } catch (caught) {
      error.value = normalizeApiError(caught);
    } finally {
      clearActionPending(item.job.id);
    }
  }

  async function handleBatchRetry(): Promise<void> {
    if (!selectedItems.value.length || batchLoading.value) {
      return;
    }
    const counts = countBatchRetryable(selectedItems.value);
    try {
      await ElMessageBox.confirm(
        `将对 ${selectedItems.value.length} 个已选异常执行批量重试；其中可重试 ${counts.retryable} 个，不可重试 ${counts.nonRetryable} 个会被后端跳过。`,
        "确认批量重试",
        {
          confirmButtonText: "执行重试",
          cancelButtonText: "返回",
          type: "warning",
        },
      );
    } catch (caught) {
      if (caught === "cancel" || caught === "close") {
        return;
      }
      error.value = normalizeApiError(caught);
      return;
    }
    batchLoading.value = true;
    error.value = null;
    try {
      const response = await documentJobIncidentsApi.bulkRetry({
        job_ids: selectedItems.value.map((item) => item.job.id),
        reason: "incident triage batch retry",
      });
      showBatchResult(response);
      await loadIncidents({ preserveError: true });
    } catch (caught) {
      error.value = normalizeApiError(caught);
    } finally {
      batchLoading.value = false;
    }
  }

  async function handleBatchRefresh(): Promise<void> {
    if (!selectedItems.value.length || batchLoading.value) {
      return;
    }
    batchLoading.value = true;
    error.value = null;
    try {
      const response = await documentJobIncidentsApi.bulkRefresh({
        job_ids: selectedItems.value.map((item) => item.job.id),
      });
      showBatchResult(response);
      await loadIncidents({ preserveError: true });
    } catch (caught) {
      error.value = normalizeApiError(caught);
    } finally {
      batchLoading.value = false;
    }
  }

  function showBatchResult(result: DocumentJobIncidentBulkResponse): void {
    batchResult.value = result;
    batchResultExpanded.value = result.failed > 0 || result.skipped > 0;
    if (result.failed > 0 || result.skipped > 0) {
      ElMessage.warning(`${batchResultActionLabel.value}完成：成功 ${result.succeeded}，失败 ${result.failed}，跳过 ${result.skipped}。`);
      return;
    }
    ElMessage.success(`${batchResultActionLabel.value}完成：成功 ${result.succeeded}。`);
  }

  function reselectFailedItems(): void {
    const failedIds = new Set(failedBatchItems.value.map((item) => item.job_id));
    table.clearSelection();
    for (const item of items.value) {
      if (failedIds.has(item.job.id)) {
        table.toggleRowSelection(item, true);
      }
    }
  }

  return {
    batchLoading,
    batchResult,
    batchResultExpanded,
    actionPending,
    selectedRetryableCount,
    selectedNonRetryableCount,
    failedBatchItems,
    normalizedBatchResult,
    clearBatchResult,
    isActionBusy,
    handleSingleRetry,
    handleBatchRetry,
    handleBatchRefresh,
    reselectFailedItems,
  };
}

export type IncidentActions = ReturnType<typeof useIncidentActions>;
