// 异常队列数据 owner：筛选状态、URL query 同步（含抽屉的 incident_job_id 写回）、列表加载、自动刷新与保存视图应用。
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { ElMessage } from "element-plus";
import type { RouteLocationNormalizedLoaded, Router } from "vue-router";

import { documentJobIncidentsApi } from "@/api/documentJobIncidents";
import type {
  DocumentJobIncidentFailureType,
  DocumentJobIncidentQueueItemResponse,
  DocumentJobIncidentRetryCountBucket,
  DocumentJobIncidentSort,
  DocumentJobIncidentSummaryResponse,
  DocumentJobStage,
  DocumentJobStatus,
} from "@/api/types";
import { useWorkbenchSavedViews } from "@/composables/useWorkbenchSavedViews";
import { normalizeApiError, type ApiClientError } from "@/utils/errors";
import {
  activeSavedViewId,
  hasMeaningfulSavedViewQuery,
  incidentsSavedViewStateToQuery,
  personalSavedViewToStripItem,
  systemSavedViews,
  type SavedViewStripItem,
} from "@/utils/savedViews";
import {
  getStoredWorkbenchTablePreferences,
  INCIDENT_TABLE_COLUMNS,
  isWorkbenchTableColumnVisible,
  persistWorkbenchTablePreferences,
  resetWorkbenchTablePreferences,
  type WorkbenchTablePreferences,
} from "@/utils/tablePreferences";
import {
  buildIncidentFilterChips,
  buildIncidentRouteQuery,
  countAdvancedIncidentFilters,
  DEFAULT_STALLED_FILTER,
  describeIncidentFilters,
  hasActiveIncidentFilters,
  incidentSavedViewState,
  isSameIncidentFilterRouteQuery,
  isSameIncidentRouteQuery,
  parseIncidentRouteQuery,
  type FilterChipKey,
  type IncidentFilters,
  type SummaryFilter,
} from "./incidentQuery";

const AUTO_REFRESH_MS = 12000;

export function useIncidentQueue(
  route: RouteLocationNormalizedLoaded,
  router: Router,
  options: {
    // 抽屉当前打开的任务；写入 URL 时随筛选一起保留。
    selectedIncidentJobId: () => string;
    // 路由 incident_job_id 变化后由抽屉 owner 打开或关闭诊断。
    onRouteDiagnosticSync: () => void;
    // 筛选、分页或应用视图时清空上一次批量结果；结果本身由 useIncidentActions 持有。
    onResultReset: () => void;
    // 抽屉打开或批量处理中暂停后台刷新。
    canAutoRefresh: () => boolean;
    // 列显示变化后让表格重新计算列宽。
    onTableLayout: () => void;
  },
) {
  const items = ref<DocumentJobIncidentQueueItemResponse[]>([]);
  const loading = ref(false);
  const backgroundRefreshing = ref(false);
  const error = ref<ApiClientError | null>(null);
  const page = ref(1);
  const incidentTableColumns = INCIDENT_TABLE_COLUMNS;
  const tablePreferences = ref(getStoredWorkbenchTablePreferences("incidents", incidentTableColumns));
  const pageSize = computed(() => tablePreferences.value.pageSize);
  const total = ref(0);
  const summary = ref<DocumentJobIncidentSummaryResponse | null>(null);
  const statusFilter = ref<DocumentJobStatus | "">("");
  const stageFilter = ref<DocumentJobStage | "">("");
  const failureTypeFilter = ref<DocumentJobIncidentFailureType | "">("");
  const retryableFilter = ref<"" | "true" | "false">("");
  const retryCountFilter = ref<DocumentJobIncidentRetryCountBucket | "">("");
  const stalledMinutesFilter = ref<number | null>(null);
  const searchKeyword = ref("");
  const sortFilter = ref<DocumentJobIncidentSort>("priority");
  const selectedItems = ref<DocumentJobIncidentQueueItemResponse[]>([]);
  const lastRefreshedAt = ref<string | null>(null);
  let refreshTimer: number | undefined;
  let routeSyncInProgress = false;

  const filters = computed<IncidentFilters>(() => ({
    status: statusFilter.value,
    stage: stageFilter.value,
    failureType: failureTypeFilter.value,
    retryable: retryableFilter.value,
    retryCount: retryCountFilter.value,
    stalledMinutes: stalledMinutesFilter.value,
    q: searchKeyword.value,
    sort: sortFilter.value,
  }));
  const incidentErrorDiagnosticContext = computed(() => ({
    route: route.fullPath,
    operation: "document_job_incidents.list",
  }));
  const syncStatusText = computed(() => (loading.value || backgroundRefreshing.value ? "同步中" : "已同步"));
  const activeFilterLabel = computed(() => describeIncidentFilters(filters.value));
  const hasActiveFilters = computed(() => hasActiveIncidentFilters(filters.value));
  const advancedFilterCount = computed(() => countAdvancedIncidentFilters(filters.value));
  const activeFilterChips = computed(() => buildIncidentFilterChips(filters.value));
  const incidentSummaryItems = computed(() => [
    {
      id: "stalled",
      label: "停滞/超时",
      helper: "优先刷新状态",
      count: summary.value?.stalled ?? 0,
      tone: "warning" as const,
      active: stalledMinutesFilter.value === DEFAULT_STALLED_FILTER,
    },
    {
      id: "failed",
      label: "失败任务",
      helper: "按可重试性分流",
      count: summary.value?.failed ?? 0,
      tone: "danger" as const,
      active: statusFilter.value === "failed",
    },
    {
      id: "retryable",
      label: "可直接重试",
      helper: "批量确认后执行",
      count: summary.value?.retryable ?? 0,
      tone: "info" as const,
      active: retryableFilter.value === "true",
    },
    {
      id: "artifact",
      label: "产物缺失",
      helper: "先看证据",
      count: summary.value?.by_failure_type?.artifact_missing ?? 0,
      tone: "danger" as const,
      active: failureTypeFilter.value === "artifact_missing",
    },
  ]);

  const currentSavedViewState = computed(() => incidentSavedViewState(filters.value));
  const savedViewStore = useWorkbenchSavedViews("incidents", currentSavedViewState, handleSavedViewError);
  const { savedViews, loadSavedViews } = savedViewStore;
  const incidentSystemSavedViews = systemSavedViews.incidents;
  const personalSavedViewItems = computed(() => savedViews.value.map(personalSavedViewToStripItem));
  const allSavedViewItems = computed(() => [...incidentSystemSavedViews, ...personalSavedViewItems.value]);
  const activeSavedView = computed(() => activeSavedViewId(currentSavedViewState.value, allSavedViewItems.value));

  // 已有请求进行中时直接跳过，不排队也不取消（沿用页面既有行为）。
  async function loadIncidents(loadOptions: { background?: boolean; preserveError?: boolean } = {}): Promise<void> {
    if (loading.value || backgroundRefreshing.value) {
      return;
    }
    if (loadOptions.background) {
      backgroundRefreshing.value = true;
    } else {
      loading.value = true;
    }
    if (!loadOptions.preserveError) {
      error.value = null;
    }
    try {
      const response = await documentJobIncidentsApi.list({
        page: page.value,
        page_size: pageSize.value,
        status: statusFilter.value || undefined,
        stage: stageFilter.value || undefined,
        failure_type: failureTypeFilter.value || undefined,
        retryable: retryableFilter.value ? retryableFilter.value === "true" : undefined,
        retry_count: retryCountFilter.value || undefined,
        stalled_minutes: stalledMinutesFilter.value || undefined,
        q: searchKeyword.value.trim() || undefined,
        sort: sortFilter.value,
      });
      items.value = response.items;
      total.value = response.total;
      summary.value = response.summary;
      selectedItems.value = [];
      lastRefreshedAt.value = new Date().toISOString();
    } catch (caught) {
      error.value = normalizeApiError(caught);
    } finally {
      if (loadOptions.background) {
        backgroundRefreshing.value = false;
      } else {
        loading.value = false;
      }
    }
  }

  async function initializeSavedViewsAndLoad(): Promise<void> {
    applyRouteQueryFilters();
    options.onRouteDiagnosticSync();
    await loadSavedViews();
    const defaultView = savedViews.value.find((view) => view.is_default);
    if (defaultView && !hasMeaningfulSavedViewQuery(route.query, "incidents")) {
      await applySavedView(personalSavedViewToStripItem(defaultView), true);
      return;
    }
    await syncRouteAndLoad(page.value, true);
  }

  async function applySavedView(view: SavedViewStripItem, replace = false): Promise<void> {
    options.onResultReset();
    const query = incidentsSavedViewStateToQuery(view, 1, options.selectedIncidentJobId());
    if (!isSameIncidentRouteQuery(route.query, query)) {
      await navigateWithoutReload(query, replace);
    }
    applyRouteQueryFilters();
    await loadIncidents();
  }

  function handleSavedViewError(caught: unknown): void {
    const normalized = normalizeApiError(caught);
    error.value = normalized;
    ElMessage.error(normalized.message);
  }

  function applyRouteQueryFilters(): void {
    const parsed = parseIncidentRouteQuery(route.query);
    statusFilter.value = parsed.status;
    stageFilter.value = parsed.stage;
    failureTypeFilter.value = parsed.failureType;
    retryableFilter.value = parsed.retryable;
    retryCountFilter.value = parsed.retryCount;
    stalledMinutesFilter.value = parsed.stalledMinutes;
    searchKeyword.value = parsed.q;
    sortFilter.value = parsed.sort;
    page.value = parsed.page;
  }

  // 本页主动改路由时标记同步中，避免 route.query watcher 重复加载或重复同步抽屉。
  async function navigateWithoutReload(query: Record<string, string>, replace: boolean): Promise<void> {
    routeSyncInProgress = true;
    try {
      await router[replace ? "replace" : "push"]({ name: "incidents", query });
    } finally {
      routeSyncInProgress = false;
    }
  }

  async function syncRouteAndLoad(nextPage: number, replace = false): Promise<void> {
    page.value = nextPage;
    const query = buildIncidentRouteQuery(filters.value, nextPage, options.selectedIncidentJobId());
    if (!isSameIncidentRouteQuery(route.query, query)) {
      await navigateWithoutReload(query, replace);
    }
    await loadIncidents();
  }

  async function replaceIncidentJobQuery(jobId: string | null): Promise<void> {
    const query = buildIncidentRouteQuery(filters.value, page.value, jobId);
    if (isSameIncidentRouteQuery(route.query, query)) {
      return;
    }
    await navigateWithoutReload(query, true);
  }

  function handleFilter(): void {
    options.onResultReset();
    void syncRouteAndLoad(1);
  }

  function handlePageChange(nextPage: number): void {
    void syncRouteAndLoad(nextPage);
  }

  function isTableColumnVisible(columnId: string): boolean {
    return isWorkbenchTableColumnVisible(tablePreferences.value, columnId);
  }

  function applyTablePreferences(nextPreferences: WorkbenchTablePreferences): void {
    const previousPageSize = tablePreferences.value.pageSize;
    tablePreferences.value = nextPreferences;
    options.onTableLayout();
    if (tablePreferences.value.pageSize !== previousPageSize) {
      options.onResultReset();
      void syncRouteAndLoad(1);
    }
  }

  function handleTablePreferencesUpdate(nextPreferences: WorkbenchTablePreferences): void {
    applyTablePreferences(persistWorkbenchTablePreferences("incidents", nextPreferences, incidentTableColumns));
  }

  function handleTablePreferencesReset(): void {
    applyTablePreferences(resetWorkbenchTablePreferences("incidents", incidentTableColumns));
  }

  function resetAllFilters(): void {
    statusFilter.value = "";
    stageFilter.value = "";
    failureTypeFilter.value = "";
    retryableFilter.value = "";
    retryCountFilter.value = "";
    stalledMinutesFilter.value = null;
    searchKeyword.value = "";
    sortFilter.value = "priority";
  }

  function applySummaryFilter(kind: SummaryFilter): void {
    resetAllFilters();
    if (kind === "stalled") {
      stalledMinutesFilter.value = DEFAULT_STALLED_FILTER;
    } else if (kind === "failed") {
      statusFilter.value = "failed";
    } else if (kind === "retryable") {
      retryableFilter.value = "true";
    } else {
      failureTypeFilter.value = "artifact_missing";
    }
    handleFilter();
  }

  function handleIncidentSummarySelect(kind: string): void {
    applySummaryFilter(kind as SummaryFilter);
  }

  function resetAdvancedFilters(): void {
    retryCountFilter.value = "";
    stalledMinutesFilter.value = null;
    sortFilter.value = "priority";
    handleFilter();
  }

  function clearIncidentFilters(): void {
    resetAllFilters();
    handleFilter();
  }

  function removeFilter(key: FilterChipKey): void {
    if (key === "status") {
      statusFilter.value = "";
    } else if (key === "stage") {
      stageFilter.value = "";
    } else if (key === "failure_type") {
      failureTypeFilter.value = "";
    } else if (key === "retryable") {
      retryableFilter.value = "";
    } else if (key === "retry_count") {
      retryCountFilter.value = "";
    } else if (key === "stalled_minutes") {
      stalledMinutesFilter.value = null;
    } else if (key === "q") {
      searchKeyword.value = "";
    } else {
      sortFilter.value = "priority";
    }
    handleFilter();
  }

  function handleSelectionChange(selection: DocumentJobIncidentQueueItemResponse[]): void {
    selectedItems.value = selection;
  }

  function startAutoRefresh(): void {
    refreshTimer = window.setInterval(() => {
      const visible = typeof document === "undefined" || !document.hidden;
      if (visible && options.canAutoRefresh()) {
        void loadIncidents({ background: true, preserveError: true });
      }
    }, AUTO_REFRESH_MS);
  }

  watch(
    () => route.query,
    (nextQuery, previousQuery) => {
      applyRouteQueryFilters();
      if (!routeSyncInProgress && !isSameIncidentFilterRouteQuery(nextQuery, previousQuery)) {
        void loadIncidents();
      }
      if (!routeSyncInProgress) {
        options.onRouteDiagnosticSync();
      }
    },
  );

  onMounted(() => {
    void initializeSavedViewsAndLoad();
    startAutoRefresh();
  });

  onBeforeUnmount(() => {
    if (refreshTimer !== undefined) {
      window.clearInterval(refreshTimer);
    }
  });

  return {
    ...savedViewStore,
    items,
    loading,
    backgroundRefreshing,
    error,
    page,
    pageSize,
    total,
    incidentTableColumns,
    tablePreferences,
    statusFilter,
    stageFilter,
    failureTypeFilter,
    retryableFilter,
    retryCountFilter,
    stalledMinutesFilter,
    searchKeyword,
    sortFilter,
    selectedItems,
    lastRefreshedAt,
    incidentErrorDiagnosticContext,
    syncStatusText,
    activeFilterLabel,
    hasActiveFilters,
    advancedFilterCount,
    activeFilterChips,
    incidentSummaryItems,
    incidentSystemSavedViews,
    personalSavedViewItems,
    activeSavedView,
    loadIncidents,
    applySavedView,
    replaceIncidentJobQuery,
    handleFilter,
    handlePageChange,
    isTableColumnVisible,
    handleTablePreferencesUpdate,
    handleTablePreferencesReset,
    handleIncidentSummarySelect,
    resetAdvancedFilters,
    clearIncidentFilters,
    removeFilter,
    handleSelectionChange,
  };
}

export type IncidentQueue = ReturnType<typeof useIncidentQueue>;
