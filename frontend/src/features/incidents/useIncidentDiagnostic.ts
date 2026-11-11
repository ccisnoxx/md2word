// 异常诊断抽屉 owner：当前任务、抽屉开关、诊断加载（令牌防止旧响应覆盖）及与 incident_job_id 的同步。
import { computed, ref, type Ref } from "vue";
import type { RouteLocationNormalizedLoaded, Router } from "vue-router";

import { documentJobIncidentsApi } from "@/api/documentJobIncidents";
import type { DocumentJobIncidentDiagnosticResponse, DocumentJobIncidentQueueItemResponse } from "@/api/types";
import type { EvidenceKeyValueItem } from "@/components/EvidenceKeyValueList.vue";
import { normalizeApiError, type ApiClientError } from "@/utils/errors";
import { jobFailureSummaryLines } from "@/utils/failureDiagnostic";
import { formatDateTime, getJobSourceFilename } from "@/utils/format";
import { buildIncidentDiagnosticGuidance } from "@/utils/incidents";
import { firstQueryValue } from "./incidentQuery";

export function useIncidentDiagnostic(
  route: RouteLocationNormalizedLoaded,
  router: Router,
  deps: {
    items: Ref<DocumentJobIncidentQueueItemResponse[]>;
    // URL 写入统一由队列 owner 完成，抽屉只声明要保留或清除的任务。
    replaceIncidentJobQuery: (jobId: string | null) => Promise<void>;
  },
) {
  const activeJobId = ref("");
  const selectedIncidentJobId = ref("");
  const drawerVisible = ref(false);
  const drawerLoading = ref(false);
  const drawerError = ref<ApiClientError | null>(null);
  const diagnostic = ref<DocumentJobIncidentDiagnosticResponse | null>(null);
  const drawerSize = "min(760px, 94vw)";
  let drawerLoadToken = 0;

  const drawerErrorDiagnosticContext = computed(() => ({
    route: route.fullPath,
    operation: "document_job_incidents.diagnostics",
    job_id: selectedIncidentJobId.value,
  }));
  const diagnosticTitle = computed(() => diagnostic.value?.item.job.id || selectedIncidentJobId.value || "异常诊断");
  const incidentDiagnosticGuidance = computed(() =>
    diagnostic.value ? buildIncidentDiagnosticGuidance(diagnostic.value.item) : null,
  );
  const latestDiagnosticTraceId = computed(() =>
    [...(diagnostic.value?.recent_events || [])].reverse().find((event) => event.trace_id)?.trace_id || "-",
  );
  const incidentKeyEvidenceItems = computed<EvidenceKeyValueItem[]>(() => {
    if (!diagnostic.value) {
      return [];
    }
    const failureLocation = jobFailureSummaryLines(diagnostic.value.item.job, diagnostic.value.failure_diagnostic, true);
    return [
      { label: "任务 ID", value: diagnostic.value.item.job.id, mono: true },
      { label: "文件", value: getJobSourceFilename(diagnostic.value.item.job) },
      {
        label: "错误",
        value: `${diagnostic.value.item.job.error_code || "-"} · ${diagnostic.value.item.job.error_message || "-"}`,
      },
      ...(failureLocation.length ? [{ label: "失败摘要", value: failureLocation.join("；") }] : []),
      {
        label: "时间",
        value: `创建 ${formatDateTime(diagnostic.value.item.job.created_at)} · 更新 ${formatDateTime(diagnostic.value.item.job.updated_at)}`,
      },
      { label: "trace_id", value: latestDiagnosticTraceId.value, mono: true },
    ];
  });

  function incidentRowClassName({ row }: { row: DocumentJobIncidentQueueItemResponse }): string {
    return row.job.id === activeJobId.value ? "is-active-incident-row" : "";
  }

  async function openDiagnostic(item: DocumentJobIncidentQueueItemResponse): Promise<void> {
    activeJobId.value = item.job.id;
    selectedIncidentJobId.value = item.job.id;
    drawerVisible.value = true;
    await deps.replaceIncidentJobQuery(item.job.id);
    await loadDiagnostics(item.job.id);
  }

  function openDiagnosticFromRoute(jobId: string): void {
    activeJobId.value = jobId;
    selectedIncidentJobId.value = jobId;
    drawerVisible.value = true;
    void loadDiagnostics(jobId);
  }

  async function loadDiagnostics(jobId: string): Promise<void> {
    const loadToken = ++drawerLoadToken;
    drawerLoading.value = true;
    drawerError.value = null;
    try {
      const response = await documentJobIncidentsApi.getDiagnostics(jobId);
      if (loadToken !== drawerLoadToken || selectedIncidentJobId.value !== jobId) {
        return;
      }
      diagnostic.value = response;
    } catch (caught) {
      if (loadToken === drawerLoadToken && selectedIncidentJobId.value === jobId) {
        drawerError.value = normalizeApiError(caught);
      }
    } finally {
      if (loadToken === drawerLoadToken && selectedIncidentJobId.value === jobId) {
        drawerLoading.value = false;
      }
    }
  }

  async function refreshDiagnostic(): Promise<void> {
    if (!selectedIncidentJobId.value) {
      return;
    }
    await loadDiagnostics(selectedIncidentJobId.value);
  }

  async function closeDiagnostic(): Promise<void> {
    drawerLoadToken += 1;
    selectedIncidentJobId.value = "";
    drawerVisible.value = false;
    drawerLoading.value = false;
    drawerError.value = null;
    diagnostic.value = null;
    await deps.replaceIncidentJobQuery(null);
  }

  function handleDrawerModelValue(nextValue: boolean): void {
    if (!nextValue) {
      void closeDiagnostic();
    }
  }

  function syncDiagnosticFromRoute(): void {
    const routeJobId = firstQueryValue(route.query.incident_job_id);
    if (!routeJobId) {
      if (selectedIncidentJobId.value) {
        void closeDiagnostic();
      }
      return;
    }
    if (routeJobId !== selectedIncidentJobId.value || !drawerVisible.value) {
      openDiagnosticFromRoute(routeJobId);
    }
  }

  function openJobDetail(item: DocumentJobIncidentQueueItemResponse): void {
    void router.push({ name: "job-detail", params: { jobId: item.job.id } });
  }

  function openSelectedJobDetail(): void {
    if (!selectedIncidentJobId.value) {
      return;
    }
    void router.push({ name: "job-detail", params: { jobId: selectedIncidentJobId.value } });
  }

  // J/K 在当前队列内移动高亮行；抽屉打开时同步切换诊断对象。
  function selectAdjacentIncident(delta: number): void {
    const items = deps.items.value;
    if (!items.length) {
      return;
    }
    const currentId = selectedIncidentJobId.value || activeJobId.value;
    const currentIndex = Math.max(0, items.findIndex((item) => item.job.id === currentId));
    const nextIndex = Math.min(Math.max(currentIndex + delta, 0), items.length - 1);
    const nextItem = items[nextIndex];
    activeJobId.value = nextItem.job.id;
    if (drawerVisible.value) {
      void openDiagnostic(nextItem);
    }
  }

  return {
    selectedIncidentJobId,
    drawerVisible,
    drawerLoading,
    drawerError,
    diagnostic,
    drawerSize,
    drawerErrorDiagnosticContext,
    diagnosticTitle,
    incidentDiagnosticGuidance,
    incidentKeyEvidenceItems,
    incidentRowClassName,
    openDiagnostic,
    loadDiagnostics,
    refreshDiagnostic,
    closeDiagnostic,
    handleDrawerModelValue,
    syncDiagnosticFromRoute,
    openJobDetail,
    openSelectedJobDetail,
    selectAdjacentIncident,
  };
}

export type IncidentDiagnostic = ReturnType<typeof useIncidentDiagnostic>;
