import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import type {
  DocumentFileSummaryResponse,
  DocumentJobCallbackMessageSummaryResponse,
  DocumentJobEventResponse,
  DocumentJobResponse,
  DocumentJobStage,
  DocumentJobTranslationBatchExecutionResponse,
  DocumentJobTranslationBatchSummaryResponse,
  DocumentQualitySourceResponse,
  DocumentReviewBlocksResponse,
} from "@/api/types";
import { documentJobsApi } from "@/api/documentJobs";
import { isActiveJobStatus } from "@/utils/format";
import { normalizeApiError, type ApiClientError } from "@/utils/errors";
import { supportsJobTranslationQa, usesTranslationResources } from "./jobDetailFormat";
import type { RouteLocationNormalizedLoaded } from "vue-router";

interface DetailLifecycle {
  onRetryRequested: (job: DocumentJobResponse) => void;
  onRouteReset: () => void;
}

// 每个页面实例仅创建一个数据 owner；动作共享这里的任务引用，展示投影不发起请求。
export function useJobDetailData(
  route: Pick<RouteLocationNormalizedLoaded, "params" | "query" | "fullPath">,
  lifecycle: DetailLifecycle,
) {
  const jobId = computed(() => String(route.params.jobId || ""));
  const job = ref<DocumentJobResponse | null>(null);

  const events = ref<DocumentJobEventResponse[]>([]);

  const files = ref<DocumentFileSummaryResponse[]>([]);

  const callbackSummary = ref<DocumentJobCallbackMessageSummaryResponse | null>(null);

  const translationBatches = ref<DocumentJobTranslationBatchSummaryResponse[]>([]);

  const translationBatchGeneration = ref<number | null>(null);

  const translationBatchExecution = ref<DocumentJobTranslationBatchExecutionResponse | null | undefined>(undefined);

  const reviewBlocks = ref<DocumentReviewBlocksResponse | null>(null);

  const reviewBlocksLoading = ref(false);
  const reviewBlocksError = ref<ApiClientError | null>(null);

  const reviewBlocksConflict = ref(false);
  const loading = ref(false);
  const eventsLoading = ref(false);
  const filesLoading = ref(false);
  const callbackSummaryLoading = ref(false);
  const translationBatchesLoading = ref(false);
  const activeTab = ref("overview");
  const eventLevelFilter = ref<"" | "info" | "warning" | "error">("");

  const eventStageFilter = ref<DocumentJobStage | "">("");

  const error = ref<ApiClientError | null>(null);

  const eventsError = ref<ApiClientError | null>(null);

  const filesError = ref<ApiClientError | null>(null);

  const callbackSummaryError = ref<ApiClientError | null>(null);

  const translationBatchesError = ref<ApiClientError | null>(null);

  let pollTimer: number | undefined;

  let pollRefreshCount = 0;

  let disposed = false;

  let routeEpoch = 0;

  const requestRounds = { all: 0, job: 0, events: 0, files: 0, callbackSummary: 0, translationBatches: 0, reviewBlocks: 0 };

  const reviewHintsAvailable = computed(() => reviewBlocks.value?.availability === "available" && !reviewBlocksError.value && !reviewBlocksConflict.value);

  async function loadJob(targetJobId = jobId.value): Promise<void> {
    if (disposed || targetJobId !== jobId.value) {
      return;
    }
    const requestRound = ++requestRounds.job;
    loading.value = true;
    error.value = null;
    try {
      const response = await documentJobsApi.get(targetJobId);
      if (isCurrentRequest("job", requestRound, targetJobId)) {
        job.value = response;
      }
    } catch (caught) {
      if (isCurrentRequest("job", requestRound, targetJobId)) {
        error.value = normalizeApiError(caught);
      }
    } finally {
      if (isCurrentRequest("job", requestRound, targetJobId)) {
        loading.value = false;
      }
    }
  }

  async function loadEvents(targetJobId = jobId.value): Promise<void> {
    if (disposed || targetJobId !== jobId.value) {
      return;
    }
    const requestRound = ++requestRounds.events;
    eventsLoading.value = true;
    eventsError.value = null;
    try {
      const response = await documentJobsApi.listEvents(targetJobId);
      if (isCurrentRequest("events", requestRound, targetJobId)) {
        events.value = response.items;
      }
    } catch (caught) {
      if (isCurrentRequest("events", requestRound, targetJobId)) {
        eventsError.value = normalizeApiError(caught);
      }
    } finally {
      if (isCurrentRequest("events", requestRound, targetJobId)) {
        eventsLoading.value = false;
      }
    }
  }

  async function loadFiles(targetJobId = jobId.value): Promise<void> {
    if (disposed || targetJobId !== jobId.value) {
      return;
    }
    const requestRound = ++requestRounds.files;
    filesLoading.value = true;
    filesError.value = null;
    try {
      const response = await documentJobsApi.listFiles(targetJobId);
      if (isCurrentRequest("files", requestRound, targetJobId)) {
        files.value = response.files;
      }
    } catch (caught) {
      if (isCurrentRequest("files", requestRound, targetJobId)) {
        filesError.value = normalizeApiError(caught);
      }
    } finally {
      if (isCurrentRequest("files", requestRound, targetJobId)) {
        filesLoading.value = false;
      }
    }
  }

  async function loadCallbackSummary(targetJobId = jobId.value): Promise<void> {
    if (disposed || targetJobId !== jobId.value) {
      return;
    }
    const requestRound = ++requestRounds.callbackSummary;
    callbackSummaryLoading.value = true;
    callbackSummaryError.value = null;
    try {
      const response = await documentJobsApi.getCallbackMessageSummary(targetJobId);
      if (isCurrentRequest("callbackSummary", requestRound, targetJobId)) {
        callbackSummary.value = response;
      }
    } catch (caught) {
      if (isCurrentRequest("callbackSummary", requestRound, targetJobId)) {
        callbackSummaryError.value = normalizeApiError(caught);
      }
    } finally {
      if (isCurrentRequest("callbackSummary", requestRound, targetJobId)) {
        callbackSummaryLoading.value = false;
      }
    }
  }

  function reviewContentBinding(target: DocumentJobResponse | null): string | null {
    return target ? JSON.stringify({
      id: target.id, generation: target.retry_count, source_ir_file_id: target.source_document_ir_file_id,
      final_ir_file_id: target.document_ir_file_id, result_file_id: target.result_file_id, source_pdf_file_id: target.source_file_id,
    }) : null;
  }

  function reviewSourceKey(source: DocumentQualitySourceResponse): string {
    return JSON.stringify([source.generation, source.ir_file_id, source.result_file_id,
      source.result_sha256, source.file_review_source_revision, source.receipt_sha256]);
  }

  function resetReviewBlocks(): void {
    requestRounds.reviewBlocks += 1;
    reviewBlocks.value = null;
    reviewBlocksLoading.value = false;
    reviewBlocksError.value = null;
    reviewBlocksConflict.value = false;
  }

  async function loadReviewBlocks(append = false, targetJobId = jobId.value): Promise<void> {
    const target = job.value;
    if (disposed || targetJobId !== jobId.value || !target || target.id !== targetJobId) {
      return;
    }
    const previous = append ? reviewBlocks.value : null;
    if (append && (reviewBlocksLoading.value || !reviewHintsAvailable.value || !previous?.next_cursor)) {
      return;
    }
    const binding = reviewContentBinding(target);
    // direct 的基准 IR 即源内容；只有翻译快照单独公开 source/final 两个指针。
    const basisId = target.document_ir_file_id || target.source_document_ir_file_id;
    const isTranslation = usesTranslationResources(target);
    const requestRound = ++requestRounds.reviewBlocks;
    const isCurrent = () => isCurrentRequest("reviewBlocks", requestRound, targetJobId)
      && binding === reviewContentBinding(job.value);
    reviewBlocksLoading.value = true;
    reviewBlocksError.value = null;
    reviewBlocksConflict.value = false;
    if (!append) {
      reviewBlocks.value = null;
    }
    try {
      const response = await documentJobsApi.listReviewBlocks(targetJobId, {
        limit: 50,
        problem: "flagged",
        ...(previous?.next_cursor ? { cursor: previous.next_cursor } : {}),
      });
      if (!isCurrent()) {
        return;
      }
      // 同任务也会换代或更换产物；分页只能沿同一公开来源和内容快照继续。
      if (target.source_document_ir_file_id === undefined || response.job_id !== targetJobId || response.source.generation !== target.retry_count
        || response.source.ir_file_id !== target.document_ir_file_id || response.source.result_file_id !== target.result_file_id
        || response.content_snapshot.source_pdf_file_id !== target.source_file_id
        || response.content_snapshot.source_ir_file_id !== (isTranslation ? target.source_document_ir_file_id : basisId)
        || response.content_snapshot.final_ir_file_id !== (isTranslation ? target.document_ir_file_id : null)
        || response.content_snapshot.basis !== (!basisId ? "none" : target.document_ir_file_id ? "final" : "source")
        || (previous && (reviewSourceKey(response.source) !== reviewSourceKey(previous.source)
          || response.content_snapshot.snapshot_id !== previous.content_snapshot.snapshot_id))) {
        reviewBlocks.value = null;
        reviewBlocksConflict.value = true;
        return;
      }
      reviewBlocks.value = previous && response.availability === "available"
        ? { ...response, items: [...previous.items, ...response.items] }
        : response;
    } catch (caught) {
      if (isCurrent()) {
        reviewBlocks.value = null;
        reviewBlocksError.value = normalizeApiError(caught);
      }
    } finally {
      if (isCurrent()) {
        reviewBlocksLoading.value = false;
      }
    }
  }

  async function loadTranslationBatches(targetJobId = jobId.value): Promise<void> {
    if (disposed || targetJobId !== jobId.value) {
      return;
    }
    const requestRound = ++requestRounds.translationBatches;
    if (!supportsJobTranslationQa(job.value)) {
      translationBatches.value = [];
      translationBatchGeneration.value = null;
      translationBatchExecution.value = undefined;
      translationBatchesError.value = null;
      translationBatchesLoading.value = false;
      return;
    }
    translationBatchesLoading.value = true;
    translationBatchesError.value = null;
    try {
      const response = await documentJobsApi.listTranslationBatches(targetJobId);
      const isCurrentGeneration = job.value?.retry_count === undefined || response.generation === job.value.retry_count;
      if (isCurrentRequest("translationBatches", requestRound, targetJobId) && isCurrentGeneration) {
        translationBatches.value = response.items;
        translationBatchGeneration.value = response.generation;
        translationBatchExecution.value = response.execution;
      }
    } catch (caught) {
      if (isCurrentRequest("translationBatches", requestRound, targetJobId)) {
        translationBatchesError.value = normalizeApiError(caught);
      }
    } finally {
      if (isCurrentRequest("translationBatches", requestRound, targetJobId)) {
        translationBatchesLoading.value = false;
      }
    }
  }

  type LoadAllOptions = {
    secondary?: "all" | "smart";
  };

  function isCurrentRequest(kind: keyof typeof requestRounds, requestRound: number, targetJobId: string): boolean {
    return !disposed && targetJobId === jobId.value && requestRound === requestRounds[kind];
  }

  function invalidateRequests(): void {
    for (const kind of Object.keys(requestRounds) as Array<keyof typeof requestRounds>) {
      requestRounds[kind] += 1;
    }
  }

  async function loadAll(options: LoadAllOptions = {}): Promise<void> {
    if (disposed) {
      return;
    }
    const requestRound = ++requestRounds.all;
    const targetJobId = jobId.value;
    await loadJob(targetJobId);
    if (!isCurrentRequest("all", requestRound, targetJobId)) {
      return;
    }
    if (job.value) {
      await loadEvents(targetJobId);
      // 同一任务的新刷新也会使旧链失效，避免旧链随后启动新的子请求。
      if (!isCurrentRequest("all", requestRound, targetJobId)) {
        return;
      }
      if (options.secondary === "smart" && !shouldRefreshSecondaryDuringPoll()) {
        if (!reviewBlocks.value && !reviewBlocksLoading.value && !reviewBlocksError.value && !reviewBlocksConflict.value) {
          await loadReviewBlocks(false, targetJobId);
          if (!isCurrentRequest("all", requestRound, targetJobId)) {
            return;
          }
        }
        if (activeTab.value === "files") {
          await loadFiles(targetJobId);
        } else if (activeTab.value === "overview") {
          await loadCallbackSummary(targetJobId);
        }
        return;
      }
      const secondaryLoads = [loadFiles(targetJobId), loadCallbackSummary(targetJobId), loadReviewBlocks(false, targetJobId)];
      if (supportsJobTranslationQa(job.value)) {
        secondaryLoads.push(loadTranslationBatches(targetJobId));
      } else {
        translationBatches.value = [];
        translationBatchGeneration.value = null;
        translationBatchExecution.value = undefined;
        translationBatchesError.value = null;
      }
      await Promise.all(secondaryLoads);
    } else {
      events.value = [];
      files.value = [];
      callbackSummary.value = null;
      translationBatches.value = [];
      translationBatchGeneration.value = null;
      translationBatchExecution.value = undefined;
      eventsError.value = null;
      filesError.value = null;
      callbackSummaryError.value = null;
      translationBatchesError.value = null;
      resetReviewBlocks();
    }
  }

  function shouldRefreshSecondaryDuringPoll(): boolean {
    pollRefreshCount += 1;
    return pollRefreshCount % 3 === 0;
  }

  function stopPolling(): void {
    if (pollTimer !== undefined) {
      window.clearInterval(pollTimer);
      pollTimer = undefined;
    }
    pollRefreshCount = 0;
  }

  function syncPolling(): void {
    stopPolling();
    if (disposed || !job.value || !isActiveJobStatus(job.value.status) || document.hidden) {
      return;
    }
    pollTimer = window.setInterval(() => {
      if (loading.value || eventsLoading.value || filesLoading.value || callbackSummaryLoading.value || translationBatchesLoading.value || reviewBlocksLoading.value) {
        return;
      }
      void loadAll({ secondary: "smart" });
    }, 4000);
  }

  function handleVisibilityChange(): void {
    syncPolling();
  }

  function resetPageStateForRouteChange(): void {
    stopPolling();
    routeEpoch += 1;
    invalidateRequests();
    resetReviewBlocks();
    loading.value = false;
    eventsLoading.value = false;
    filesLoading.value = false;
    callbackSummaryLoading.value = false;
    translationBatchesLoading.value = false;
    job.value = null;
    events.value = [];
    files.value = [];
    callbackSummary.value = null;
    translationBatches.value = [];
    translationBatchGeneration.value = null;
    translationBatchExecution.value = undefined;
    error.value = null;
    eventsError.value = null;
    filesError.value = null;
    callbackSummaryError.value = null;
    translationBatchesError.value = null;
    lifecycle.onRouteReset();
    eventLevelFilter.value = "";
    eventStageFilter.value = "";
    activeTab.value = "overview";
  }

  function jobErrorDiagnosticContext(operation: string) {
    return {
      route: route.fullPath,
      operation,
      jobId: jobId.value,
      jobStatus: job.value?.status,
      updatedAt: job.value?.updated_at,
    };
  }

  function openEventsTab(): void {
    activeTab.value = "events";
  }

  watch(() => job.value?.status, syncPolling);
  watch(() => reviewContentBinding(job.value), resetReviewBlocks, { flush: "sync" });

  watch(jobId, async (nextJobId, previousJobId) => {
    if (!nextJobId || nextJobId === previousJobId) {
      return;
    }
    resetPageStateForRouteChange();
    const currentRouteEpoch = routeEpoch;
    await loadAll();
    if (disposed || currentRouteEpoch !== routeEpoch || nextJobId !== jobId.value) {
      return;
    }
    syncPolling();
    if (route.query.retry === "1" && job.value?.status === "failed") {
      lifecycle.onRetryRequested(job.value);
    }
  });

  onMounted(async () => {
    document.addEventListener("visibilitychange", handleVisibilityChange);
    const targetJobId = jobId.value;
    const currentRouteEpoch = routeEpoch;
    await loadAll();
    // 同路由刷新只替代请求，不能取消从列表进入时携带的重试意图。
    if (disposed || currentRouteEpoch !== routeEpoch || targetJobId !== jobId.value) {
      return;
    }
    syncPolling();
    if (route.query.retry === "1" && job.value?.status === "failed") {
      lifecycle.onRetryRequested(job.value);
    }
  });

  onBeforeUnmount(() => {
    disposed = true;
    stopPolling();
    document.removeEventListener("visibilitychange", handleVisibilityChange);
  });

  return {
    jobId,
    job,
    events,
    files,
    callbackSummary,
    translationBatches,
    translationBatchGeneration,
    translationBatchExecution,
    reviewBlocks,
    reviewBlocksLoading,
    reviewBlocksError,
    reviewBlocksConflict,
    loading,
    eventsLoading,
    filesLoading,
    callbackSummaryLoading,
    translationBatchesLoading,
    activeTab,
    eventLevelFilter,
    eventStageFilter,
    error,
    eventsError,
    filesError,
    callbackSummaryError,
    translationBatchesError,
    reviewHintsAvailable,
    loadJob,
    loadEvents,
    loadFiles,
    loadCallbackSummary,
    loadReviewBlocks,
    loadTranslationBatches,
    loadAll,
    syncPolling,
    resetPageStateForRouteChange,
    jobErrorDiagnosticContext,
    openEventsTab,
  };
}

export type JobDetailData = ReturnType<typeof useJobDetailData>;
