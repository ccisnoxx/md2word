// 任务列表数据 owner：筛选状态、URL query 同步、列表请求轮次、自动刷新和保存视图应用。
// query 同步与请求竞态防护必须集中在这里，不能拆散到展示组件中。
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { ElMessage } from "element-plus";
import type { RouteLocationNormalizedLoaded, Router } from "vue-router";

import type {
  DocumentJobListSort,
  DocumentJobResponse,
  DocumentJobStatus,
  DocumentJobStatusGroup,
  TranslationQaStatus,
} from "@/api/types";
import { documentJobsApi } from "@/api/documentJobs";
import { useWorkbenchSavedViews } from "@/composables/useWorkbenchSavedViews";
import { normalizeApiError, type ApiClientError } from "@/utils/errors";
import { formatDateTime } from "@/utils/format";
import {
  activeSavedViewId,
  hasMeaningfulSavedViewQuery,
  jobsSavedViewStateToQuery,
  personalSavedViewToStripItem,
  systemSavedViews,
  type SavedViewStripItem,
} from "@/utils/savedViews";
import {
  getStoredWorkbenchTablePreferences,
  JOBS_TABLE_COLUMNS,
  persistWorkbenchTablePreferences,
  resetWorkbenchTablePreferences,
  type WorkbenchTablePreferences,
} from "@/utils/tablePreferences";
import {
  buildActiveFilterChips,
  buildJobsRouteQuery,
  countAdvancedFilters,
  describeActiveFilters,
  hasActiveJobsFilters,
  isSameJobsRouteQuery,
  jobsSavedViewState,
  parseJobsRouteQuery,
  type FilterChipKey,
  type JobsListFilters,
  type WorkQueueKind,
} from "./jobsListQuery";

type LoadJobsOptions = {
  preserveError?: boolean;
  background?: boolean;
};

const ACTIVE_AUTO_REFRESH_MS = 8000;
const ACTIVE_STALE_MS = 10 * 60 * 1000;
const activeJobStatuses: DocumentJobStatus[] = ["pending", "queued", "running"];

export function useJobsList(
  route: RouteLocationNormalizedLoaded,
  router: Router,
  // 筛选、分页或路由变化时清空上一次批量结果；结果本身由 useJobsActions 持有。
  options: { onResultReset: () => void },
) {
  const jobs = ref<DocumentJobResponse[]>([]);
  const loading = ref(false);
  const error = ref<ApiClientError | null>(null);
  const page = ref(1);
  const jobsTableColumns = JOBS_TABLE_COLUMNS;
  const tablePreferences = ref(getStoredWorkbenchTablePreferences("jobs", jobsTableColumns));
  const pageSize = computed(() => tablePreferences.value.pageSize);
  const total = ref(0);
  const statusFilter = ref<DocumentJobStatus | "">("");
  const statusGroupFilter = ref<DocumentJobStatusGroup | "">("");
  const qaStatusFilter = ref<TranslationQaStatus | "">("");
  const searchKeyword = ref("");
  const sortFilter = ref<DocumentJobListSort>("created_at_desc");
  const includeArchived = ref(false);
  const createdRange = ref<[string, string] | null>(null);
  const selectedJobs = ref<DocumentJobResponse[]>([]);
  const filteredSummary = ref<Record<string, number>>({});
  const translationQaSummary = ref<Record<TranslationQaStatus, number>>({
    unreviewed: 0,
    approved: 0,
    needs_fix: 0,
    blocked: 0,
  });
  const lastRefreshedAt = ref<string | null>(null);
  const backgroundRefreshing = ref(false);
  const nowMs = ref(Date.now());
  let refreshTimer: number | undefined;
  let routeSyncInProgress = false;
  let jobsRequestRound = 0;
  let disposed = false;

  const filters = computed<JobsListFilters>(() => ({
    status: statusFilter.value,
    statusGroup: statusGroupFilter.value,
    qaStatus: qaStatusFilter.value,
    q: searchKeyword.value,
    sort: sortFilter.value,
    includeArchived: includeArchived.value,
    createdRange: createdRange.value,
  }));
  const jobsErrorDiagnosticContext = computed(() => ({
    route: route.fullPath,
    operation: "document_jobs.list",
  }));
  const summaryEntries = computed(() => Object.entries(filteredSummary.value).filter(([, count]) => count > 0));
  const hasActiveFilters = computed(() => hasActiveJobsFilters(filters.value));
  const showEmptyState = computed(() => !loading.value && !error.value && jobs.value.length === 0);
  const advancedFilterCount = computed(() => countAdvancedFilters(filters.value));
  const activeFilterLabel = computed(() => describeActiveFilters(filters.value));
  const activeFilterChips = computed(() => buildActiveFilterChips(filters.value));
  const returnQueryForDetail = computed(() => jobsRouteQuery());
  const activeVisibleJobs = computed(() => jobs.value.filter((job) => activeJobStatuses.includes(job.status)));
  const failedVisibleJobs = computed(() => jobs.value.filter((job) => job.status === "failed"));
  const staleVisibleJobs = computed(() => activeVisibleJobs.value.filter((job) => {
    const updatedAt = new Date(job.updated_at).getTime();
    return Number.isFinite(updatedAt) && nowMs.value - updatedAt > ACTIVE_STALE_MS;
  }));
  const syncStatusText = computed(() => {
    if (loading.value || backgroundRefreshing.value) {
      return "同步中";
    }
    if (staleVisibleJobs.value.length) {
      return "有停滞";
    }
    return "已同步";
  });
  const lastRefreshedLabel = computed(() => (lastRefreshedAt.value ? `最近 ${formatDateTime(lastRefreshedAt.value)}` : ""));

  const currentSavedViewState = computed(() => jobsSavedViewState(filters.value));
  const savedViewStore = useWorkbenchSavedViews("jobs", currentSavedViewState, handleSavedViewError);
  const { savedViews, loadSavedViews } = savedViewStore;
  const jobsSystemSavedViews = systemSavedViews.jobs;
  const personalSavedViewItems = computed(() => savedViews.value.map(personalSavedViewToStripItem));
  const allSavedViewItems = computed(() => [...jobsSystemSavedViews, ...personalSavedViewItems.value]);
  const activeSavedView = computed(() => activeSavedViewId(currentSavedViewState.value, allSavedViewItems.value));

  async function loadJobs(loadOptions: LoadJobsOptions = {}): Promise<void> {
    if (disposed || (loadOptions.background && (loading.value || backgroundRefreshing.value))) {
      return;
    }
    const requestRound = ++jobsRequestRound;
    // 前台筛选接管当前状态，旧请求的响应和清理均不得再写回。
    backgroundRefreshing.value = Boolean(loadOptions.background);
    loading.value = !loadOptions.background;
    if (!loadOptions.preserveError) {
      error.value = null;
    }
    try {
      const response = await documentJobsApi.list({
        page: page.value,
        page_size: pageSize.value,
        status: statusFilter.value || undefined,
        status_group: statusGroupFilter.value || undefined,
        translation_qa_status: qaStatusFilter.value || undefined,
        q: searchKeyword.value.trim() || undefined,
        sort: sortFilter.value,
        include_archived: includeArchived.value,
        created_from: createdRange.value?.[0],
        created_to: createdRange.value?.[1],
      });
      if (disposed || requestRound !== jobsRequestRound) {
        return;
      }
      jobs.value = response.items;
      selectedJobs.value = [];
      total.value = response.total;
      filteredSummary.value = response.filtered_summary ?? response.summary;
      translationQaSummary.value = {
        unreviewed: response.translation_qa_summary?.unreviewed ?? 0,
        approved: response.translation_qa_summary?.approved ?? 0,
        needs_fix: response.translation_qa_summary?.needs_fix ?? 0,
        blocked: response.translation_qa_summary?.blocked ?? 0,
      };
      lastRefreshedAt.value = new Date().toISOString();
    } catch (caught) {
      if (!disposed && requestRound === jobsRequestRound) {
        error.value = normalizeApiError(caught);
      }
    } finally {
      if (!disposed && requestRound === jobsRequestRound) {
        backgroundRefreshing.value = false;
        loading.value = false;
      }
    }
  }

  async function initializeSavedViewsAndLoad(): Promise<void> {
    applyRouteQueryFilters();
    await loadSavedViews();
    const defaultView = savedViews.value.find((view) => view.is_default);
    if (defaultView && !hasMeaningfulSavedViewQuery(route.query, "jobs")) {
      await applySavedView(personalSavedViewToStripItem(defaultView), true);
      return;
    }
    await syncRouteAndLoad(page.value, true);
  }

  async function applySavedView(view: SavedViewStripItem, replace = false): Promise<void> {
    options.onResultReset();
    await pushQueryAndLoad(jobsSavedViewStateToQuery(view, 1), replace);
  }

  function handleSavedViewError(caught: unknown): void {
    const normalized = normalizeApiError(caught);
    error.value = normalized;
    ElMessage.error(normalized.message);
  }

  function shouldAutoRefreshJobs(): boolean {
    if (typeof document !== "undefined" && document.hidden) {
      return false;
    }
    return statusGroupFilter.value === "active" || activeVisibleJobs.value.length > 0;
  }

  function startAutoRefresh(): void {
    refreshTimer = window.setInterval(() => {
      nowMs.value = Date.now();
      if (shouldAutoRefreshJobs()) {
        void loadJobs({ preserveError: true, background: true });
      }
    }, ACTIVE_AUTO_REFRESH_MS);
  }

  function handlePageChange(nextPage: number): void {
    void syncRouteAndLoad(nextPage);
  }

  function applyTablePreferences(nextPreferences: WorkbenchTablePreferences): void {
    const previousPageSize = tablePreferences.value.pageSize;
    tablePreferences.value = nextPreferences;
    if (tablePreferences.value.pageSize !== previousPageSize) {
      options.onResultReset();
      void syncRouteAndLoad(1);
    }
  }

  function handleTablePreferencesUpdate(nextPreferences: WorkbenchTablePreferences): void {
    applyTablePreferences(persistWorkbenchTablePreferences("jobs", nextPreferences, jobsTableColumns));
  }

  function handleTablePreferencesReset(): void {
    applyTablePreferences(resetWorkbenchTablePreferences("jobs", jobsTableColumns));
  }

  function handleFilter(): void {
    options.onResultReset();
    void syncRouteAndLoad(1);
  }

  function handleStatusFilterChange(): void {
    statusGroupFilter.value = "";
    handleFilter();
  }

  function handleSelectionChange(selection: DocumentJobResponse[]): void {
    selectedJobs.value = selection;
  }

  function applyRouteQueryFilters(): void {
    const parsed = parseJobsRouteQuery(route.query);
    statusFilter.value = parsed.status;
    statusGroupFilter.value = parsed.statusGroup;
    qaStatusFilter.value = parsed.qaStatus;
    sortFilter.value = parsed.sort;
    searchKeyword.value = parsed.q;
    page.value = parsed.page;
    includeArchived.value = parsed.includeArchived;
    createdRange.value = parsed.createdRange;
  }

  function applyQuickFilter(kind: "active" | "failed" | "archived"): void {
    qaStatusFilter.value = "";
    searchKeyword.value = "";
    createdRange.value = null;
    sortFilter.value = "updated_at_desc";
    if (kind === "active") {
      statusFilter.value = "";
      statusGroupFilter.value = "active";
      includeArchived.value = false;
    } else if (kind === "failed") {
      statusGroupFilter.value = "";
      statusFilter.value = "failed";
      includeArchived.value = false;
    } else {
      statusFilter.value = "";
      statusGroupFilter.value = "";
      includeArchived.value = true;
    }
    handleFilter();
  }

  function applyWorkQueueFilter(kind: WorkQueueKind): void {
    searchKeyword.value = "";
    createdRange.value = null;
    includeArchived.value = false;
    sortFilter.value = "updated_at_desc";
    statusFilter.value = "";
    statusGroupFilter.value = "";
    qaStatusFilter.value = "";
    if (kind === "failed") {
      statusFilter.value = "failed";
    } else if (kind === "stale") {
      statusGroupFilter.value = "active";
      sortFilter.value = "updated_at_asc";
    } else if (kind === "pending_qa") {
      qaStatusFilter.value = "unreviewed";
    } else {
      qaStatusFilter.value = "blocked";
    }
    handleFilter();
  }

  function resetAdvancedFilters(): void {
    sortFilter.value = "created_at_desc";
    includeArchived.value = false;
    createdRange.value = null;
    handleFilter();
  }

  function clearAllFilters(): void {
    statusFilter.value = "";
    statusGroupFilter.value = "";
    qaStatusFilter.value = "";
    searchKeyword.value = "";
    sortFilter.value = "created_at_desc";
    includeArchived.value = false;
    createdRange.value = null;
    handleFilter();
  }

  function jobsRouteQuery(nextPage = page.value): Record<string, string> {
    return buildJobsRouteQuery(filters.value, nextPage);
  }

  // 本页主动改路由时标记同步中，避免 route.query watcher 重复加载并清掉批量结果。
  async function pushQueryAndLoad(query: Record<string, string>, replace: boolean): Promise<void> {
    if (!isSameJobsRouteQuery(route.query, query)) {
      routeSyncInProgress = true;
      try {
        await router[replace ? "replace" : "push"]({ name: "jobs", query });
      } finally {
        routeSyncInProgress = false;
      }
    }
    applyRouteQueryFilters();
    await loadJobs();
  }

  async function syncRouteAndLoad(nextPage: number, replace = false): Promise<void> {
    page.value = nextPage;
    await pushQueryAndLoad(jobsRouteQuery(nextPage), replace);
  }

  function removeFilter(key: FilterChipKey): void {
    if (key === "status") {
      statusFilter.value = "";
    } else if (key === "status_group") {
      statusGroupFilter.value = "";
    } else if (key === "translation_qa_status") {
      qaStatusFilter.value = "";
    } else if (key === "q") {
      searchKeyword.value = "";
    } else if (key === "sort") {
      sortFilter.value = "created_at_desc";
    } else if (key === "include_archived") {
      includeArchived.value = false;
    } else if (key === "created_range") {
      createdRange.value = null;
    }
    handleFilter();
  }

  watch(
    () => route.query,
    () => {
      applyRouteQueryFilters();
      if (!routeSyncInProgress) {
        options.onResultReset();
        void loadJobs();
      }
    },
    { deep: true },
  );

  onMounted(() => {
    void initializeSavedViewsAndLoad();
    startAutoRefresh();
  });

  onBeforeUnmount(() => {
    disposed = true;
    if (refreshTimer !== undefined) {
      window.clearInterval(refreshTimer);
    }
  });

  return {
    ...savedViewStore,
    jobs,
    loading,
    error,
    page,
    pageSize,
    total,
    jobsTableColumns,
    tablePreferences,
    statusFilter,
    statusGroupFilter,
    qaStatusFilter,
    searchKeyword,
    sortFilter,
    includeArchived,
    createdRange,
    selectedJobs,
    filteredSummary,
    translationQaSummary,
    lastRefreshedAt,
    backgroundRefreshing,
    jobsErrorDiagnosticContext,
    summaryEntries,
    hasActiveFilters,
    showEmptyState,
    advancedFilterCount,
    activeFilterLabel,
    activeFilterChips,
    returnQueryForDetail,
    failedVisibleJobs,
    staleVisibleJobs,
    syncStatusText,
    lastRefreshedLabel,
    jobsSystemSavedViews,
    personalSavedViewItems,
    activeSavedView,
    loadJobs,
    applySavedView,
    handlePageChange,
    handleTablePreferencesUpdate,
    handleTablePreferencesReset,
    handleFilter,
    handleStatusFilterChange,
    handleSelectionChange,
    applyQuickFilter,
    applyWorkQueueFilter,
    resetAdvancedFilters,
    clearAllFilters,
    removeFilter,
  };
}

export type JobsList = ReturnType<typeof useJobsList>;
