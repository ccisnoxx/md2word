<!-- 文件：frontend/src/pages/OperationsCockpitPage.vue -->
<!-- 用途：展示个人操作驾驶舱（8:4 主副栏），聚合待办队列、行内异常诊断、保存视图与门禁健康。 -->
<template>
  <main class="operations-cockpit-page app-page" aria-labelledby="operations-cockpit-title">
    <WorkbenchPageHeader
      title-id="operations-cockpit-title"
      kicker="运营驾驶舱"
      title="今日工作"
      description="聚合异常、翻译 QA、任务队列和个人视图，直接进入现有处理页面。"
      wide
      section-class="cockpit-command-header"
    >
      <template #actions>
        <div class="sync-pill" :class="{ 'is-loading': anyLoading }">
          <span aria-hidden="true"></span>
          <strong>{{ anyLoading ? "同步中" : "已同步" }}</strong>
          <small v-if="lastLoadedAt">{{ formatDateTime(lastLoadedAt) }}</small>
        </div>
        <el-button v-if="canCreateJob" type="primary" :icon="DocumentAdd" @click="goCreateJob">
          新建转换任务
        </el-button>
        <el-button :icon="Refresh" :loading="anyLoading" @click="loadAll">刷新</el-button>
      </template>
    </WorkbenchPageHeader>

    <section v-if="!hasAccess" class="cockpit-empty-panel app-page-shell app-page-shell--wide" aria-label="无可用工作入口">
      <div>
        <h2>当前账号没有可用的个人工作队列</h2>
        <p>需要 document_jobs 或 translation_qa 读取权限后才会显示今日工作模块。</p>
      </div>
      <RouterLink class="panel-link" :to="fallbackRoute">前往可访问页面</RouterLink>
    </section>

    <template v-else>
      <section class="priority-strip app-page-shell app-page-shell--wide app-scrollbar-transient" aria-label="优先工作">
        <RouterLink
          v-for="item in priorityItems"
          :key="item.id"
          class="priority-item"
          :class="`is-${item.tone}`"
          :to="item.to"
        >
          <span class="priority-count">{{ countText(item.count) }}</span>
          <span class="priority-copy">
            <strong>{{ item.label }}</strong>
            <small>{{ item.helper }}</small>
          </span>
        </RouterLink>
      </section>

      <div class="cockpit-main-grid app-page-shell app-page-shell--wide">
        <aside class="cockpit-rail-column">
          <section aria-label="保存视图入口">
            <WorkbenchPanelCard
              title="个人入口"
              kicker="保存视图"
              card-class="cockpit-panel"
              header-class="compact"
            >
              <template #actions>
                <el-button size="small" :icon="Refresh" :loading="savedViewsState.loading" @click="loadSavedViews">
                  刷新视图
                </el-button>
              </template>

              <div v-if="savedViewsState.loading && !savedViewEntries.length" class="compact-loading">保存视图加载中...</div>
              <div v-else class="saved-view-grid">
                <RouterLink
                  v-for="entry in savedViewEntries"
                  :key="`${entry.pageKey}:${entry.view.id}`"
                  class="saved-view-entry"
                  :to="entry.to"
                >
                  <span>{{ entry.pageLabel }}</span>
                  <strong>{{ entry.view.name }}</strong>
                  <small>{{ entry.fallback ? "系统预设入口" : "个人默认视图" }}</small>
                </RouterLink>
              </div>

              <div v-if="savedViewErrorEntries.length" class="module-error-list" aria-label="保存视图错误">
                <div v-for="[pageKey, error] in savedViewErrorEntries" :key="pageKey" class="module-error">
                  <span>{{ pageLabel(pageKey) }} 保存视图加载失败：{{ error.message }}</span>
                  <el-button size="small" text @click="loadSavedViews">重试</el-button>
                </div>
              </div>
            </WorkbenchPanelCard>
          </section>

          <section v-if="canReadSettings" aria-label="发布门禁健康">
            <WorkbenchPanelCard
              title="发布门禁健康"
              kicker="配置治理"
              card-class="cockpit-panel"
              header-class="compact"
            >
              <template #actions>
                <el-button size="small" text :loading="gateState.loading" @click="loadGateSummary">刷新</el-button>
              </template>

              <div v-if="gateState.loading && !gateSummary" class="compact-loading">门禁摘要加载中...</div>
              <div v-else-if="gateState.error" class="gate-mini-error">
                <span>配置门禁摘要暂不可用：{{ gateState.error.message }}</span>
                <RouterLink class="gate-mini-link" to="/settings">前往配置中心</RouterLink>
              </div>
              <div v-else-if="gateSummary" class="gate-mini-body">
                <div class="gate-mini-status-row">
                  <el-tag :type="gateSummary.release_gate.p0_document_jobs_ready ? 'success' : 'danger'" effect="plain">
                    P0 链路：{{ gateSummary.release_gate.p0_document_jobs_ready ? "就绪" : "阻断" }}
                  </el-tag>
                  <span class="gate-mini-counts">
                    阻断 {{ gateSummary.release_gate.blockers.length }} · 告警 {{ gateSummary.release_gate.warnings.length }}
                  </span>
                </div>
                <p v-if="firstGateMessage" class="gate-mini-hint">{{ firstGateMessage }}</p>
                <p v-else class="gate-mini-hint">当前发布门禁无待处理阻断或告警。</p>
                <RouterLink class="gate-mini-link" to="/settings">进入配置中心处理 →</RouterLink>
              </div>
            </WorkbenchPanelCard>
          </section>
        </aside>

        <section class="cockpit-queue-column" aria-label="下一步工作">
          <WorkbenchPanelCard
            title="优先处理项"
            kicker="下一步工作"
            card-class="cockpit-panel"
            header-class="compact"
          >
            <template #actions>
              <div class="module-refresh-actions">
                <el-button v-if="sourceAccess.incidents" size="small" text :loading="incidentsState.loading" @click="loadIncidentsModule">异常</el-button>
                <el-button v-if="sourceAccess.translation_qa" size="small" text :loading="qaState.loading" @click="loadQaModule">QA</el-button>
                <el-button v-if="sourceAccess.jobs" size="small" text :loading="jobsState.loading" @click="loadJobsModule">任务</el-button>
              </div>
            </template>

            <div class="preview-filter-strip" role="tablist" aria-label="待办类型筛选">
              <button
                v-for="tab in previewFilterTabs"
                :key="tab.id"
                type="button"
                role="tab"
                class="preview-filter-chip"
                :class="{ 'is-active': activePreviewFilter === tab.id }"
                :aria-selected="activePreviewFilter === tab.id"
                @click="activePreviewFilter = tab.id"
              >
                <span>{{ tab.label }}</span>
                <small>{{ tab.count }}</small>
              </button>
            </div>

            <div v-if="moduleErrorEntries.length" class="module-error-list" aria-label="队列加载错误">
              <div v-for="entry in moduleErrorEntries" :key="entry.id" class="module-error">
                <span>{{ entry.label }}加载失败：{{ entry.error.message }}</span>
                <el-button size="small" text @click="entry.retry">重试</el-button>
              </div>
            </div>

            <div v-if="previewLoading && !previewRows.length" class="compact-loading">工作队列加载中...</div>
            <div v-else-if="!filteredPreviewRows.length" class="compact-empty">
              <strong>{{ previewRows.length ? "该分类暂无待处理项" : "暂无待处理工作" }}</strong>
              <span>{{ previewRows.length ? "可切换到「全部」或从右侧保存视图进入队列。" : "可以通过保存视图进入现有页面继续巡检。" }}</span>
            </div>
            <div v-else class="preview-table app-scrollbar-persistent" role="table" aria-label="下一步工作列表">
              <div class="preview-row preview-row-head" role="row">
                <span>对象</span>
                <span>状态</span>
                <span>更新</span>
                <span>建议动作</span>
                <span>入口</span>
              </div>
              <div v-for="row in filteredPreviewRows" :key="row.id" class="preview-row" role="row">
                <div class="preview-identity">
                  <span class="source-chip" :class="`is-${row.tone}`">{{ row.sourceLabel }}</span>
                  <strong :title="row.jobName">{{ row.jobName }}</strong>
                  <small class="mono">{{ row.jobId }}</small>
                </div>
                <span class="status-text">{{ statusText(row) }}</span>
                <span>{{ formatDateTime(row.updatedAt) }}</span>
                <span>{{ row.suggestedAction }}</span>
                <div class="preview-row-actions">
                  <el-button
                    v-if="row.source === 'incident' && incidentItemByJobId.has(row.jobId)"
                    size="small"
                    text
                    type="primary"
                    @click="openCockpitDiagnostic(row.jobId)"
                  >
                    快速诊断
                  </el-button>
                  <RouterLink class="row-action" :to="row.to">打开</RouterLink>
                </div>
              </div>
            </div>
          </WorkbenchPanelCard>
        </section>
      </div>
    </template>

    <IncidentDiagnosticDrawer
      v-if="incidentDiagnostic.drawerVisible.value"
      v-bind="{
        drawerVisible: incidentDiagnostic.drawerVisible.value,
        drawerSize: incidentDiagnostic.drawerSize,
        drawerLoading: incidentDiagnostic.drawerLoading.value,
        drawerError: incidentDiagnostic.drawerError.value,
        diagnostic: incidentDiagnostic.diagnostic.value,
        diagnosticTitle: incidentDiagnostic.diagnosticTitle.value,
        selectedIncidentJobId: incidentDiagnostic.selectedIncidentJobId.value,
        drawerErrorDiagnosticContext: incidentDiagnostic.drawerErrorDiagnosticContext.value,
        incidentDiagnosticGuidance: incidentDiagnostic.incidentDiagnosticGuidance.value,
        incidentKeyEvidenceItems: incidentDiagnostic.incidentKeyEvidenceItems.value,
        actionPending: cockpitActionPending,
        handleDrawerModelValue: incidentDiagnostic.handleDrawerModelValue,
        closeDiagnostic: incidentDiagnostic.closeDiagnostic,
        refreshDiagnostic: incidentDiagnostic.refreshDiagnostic,
        openSelectedJobDetail: incidentDiagnostic.openSelectedJobDetail,
        openJobDetail: incidentDiagnostic.openJobDetail,
        handleSingleRetry: handleCockpitIncidentRetry,
      }"
    />
  </main>
</template>

<script setup lang="ts">
import { computed, defineAsyncComponent, onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import { DocumentAdd, Refresh } from "@element-plus/icons-vue";
import { useRoute, useRouter } from "vue-router";

import { configSummaryApi, type ConfigWorkbenchSummaryResponse } from "@/api/configSummary";
import { documentJobIncidentsApi } from "@/api/documentJobIncidents";
import { documentJobsApi } from "@/api/documentJobs";
import { savedViewsApi } from "@/api/savedViews";
import WorkbenchPageHeader from "@/components/WorkbenchPageHeader.vue";
import WorkbenchPanelCard from "@/components/WorkbenchPanelCard.vue";
import { useIncidentDiagnostic } from "@/features/incidents/useIncidentDiagnostic";

const IncidentDiagnosticDrawer = defineAsyncComponent(
  () => import("@/features/incidents/IncidentDiagnosticDrawer.vue"),
);
import type {
  DocumentJobIncidentQueueItemResponse,
  DocumentJobIncidentSummaryResponse,
  DocumentJobResponse,
  SavedViewPageKey,
  SavedViewResponse,
  TranslationQaStatus,
} from "@/api/types";
import { getDefaultProtectedRoute, type AppAccessContext } from "@/navigation/appShell";
import { useAuthStore } from "@/stores/auth";
import { syncIncidentsBadgeCount, syncTranslationQaBadgeCount } from "@/stores/workbenchBadges";
import { readinessCodeText } from "@/utils/displayText";
import { normalizeApiError, type ApiClientError } from "@/utils/errors";
import { formatDateTime, jobStatusText, translationQaStatusText } from "@/utils/format";
import { incidentFailureTypeText } from "@/utils/incidents";
import {
  COCKPIT_PAGE_LABELS,
  buildOperationsPreviewRows,
  buildOperationsPriorityItems,
  buildSavedViewLauncherEntries,
  cockpitSourceAccess,
  countStaleActiveJobs,
  hasCockpitSourceAccess,
  type CockpitSourceAccess,
  type OperationsPreviewRow,
  type OperationsPreviewSource,
} from "@/utils/operationsCockpit";

type LoadState = {
  loading: boolean;
  error: ApiClientError | null;
};

type ModuleErrorEntry = {
  id: string;
  label: string;
  error: ApiClientError;
  retry: () => void;
};

type PreviewFilterId = "all" | OperationsPreviewSource;

function createLoadState(): LoadState {
  return {
    loading: false,
    error: null,
  };
}

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();
const jobsState = reactive(createLoadState());
const qaState = reactive(createLoadState());
const incidentsState = reactive(createLoadState());
const savedViewsState = reactive(createLoadState());
const gateState = reactive(createLoadState());
const jobSummary = ref<Record<string, number> | null>(null);
const qaSummary = ref<Partial<Record<TranslationQaStatus, number>> | null>(null);
const incidentSummary = ref<DocumentJobIncidentSummaryResponse | null>(null);
const gateSummary = ref<ConfigWorkbenchSummaryResponse | null>(null);
const jobPreviewJobs = ref<DocumentJobResponse[]>([]);
const qaPreviewJobs = ref<DocumentJobResponse[]>([]);
const incidentItems = ref<DocumentJobIncidentQueueItemResponse[]>([]);
const savedViewsByPage = ref<Record<SavedViewPageKey, SavedViewResponse[]>>({
  jobs: [],
  translation_qa: [],
  incidents: [],
});
const savedViewErrors = ref<Partial<Record<SavedViewPageKey, ApiClientError>>>({});
const lastLoadedAt = ref<string | null>(null);
const activePreviewFilter = ref<PreviewFilterId>("all");
const cockpitActionPending = ref<Record<string, "retry" | undefined>>({});

const incidentDiagnostic = useIncidentDiagnostic(route, router, {
  items: incidentItems,
  replaceIncidentJobQuery: async () => {},
});

const access = computed<AppAccessContext>(() => ({
  role: auth.user?.role ?? null,
  roles: auth.user?.roles ?? [],
  permissions: auth.user?.permissions ?? [],
}));
const sourceAccess = computed<CockpitSourceAccess>(() => cockpitSourceAccess(access.value));
const hasAccess = computed(() => hasCockpitSourceAccess(sourceAccess.value));
const canCreateJob = computed(() => access.value.permissions.includes("document_jobs:create"));
const canReadSettings = computed(() => access.value.permissions.includes("settings:read"));
const fallbackRoute = computed(() => getDefaultProtectedRoute(access.value));
const accessiblePageKeys = computed<SavedViewPageKey[]>(() => {
  const keys: SavedViewPageKey[] = [];
  if (sourceAccess.value.jobs) {
    keys.push("jobs");
  }
  if (sourceAccess.value.translation_qa) {
    keys.push("translation_qa");
  }
  if (sourceAccess.value.incidents) {
    keys.push("incidents");
  }
  return keys;
});
const anyLoading = computed(() => jobsState.loading || qaState.loading || incidentsState.loading || savedViewsState.loading);
const previewLoading = computed(() => jobsState.loading || qaState.loading || incidentsState.loading);
const staleActiveCount = computed(() => countStaleActiveJobs(jobPreviewJobs.value));
const priorityItems = computed(() =>
  buildOperationsPriorityItems({
    access: sourceAccess.value,
    jobSummary: jobSummary.value,
    qaSummary: qaSummary.value,
    incidentSummary: incidentSummary.value,
    staleActiveCount: staleActiveCount.value,
  }),
);
const savedViewEntries = computed(() =>
  accessiblePageKeys.value.flatMap((pageKey) => buildSavedViewLauncherEntries(pageKey, savedViewsByPage.value[pageKey])),
);
const savedViewErrorEntries = computed(() => Object.entries(savedViewErrors.value) as Array<[SavedViewPageKey, ApiClientError]>);
const previewRows = computed(() =>
  buildOperationsPreviewRows({
    incidentItems: sourceAccess.value.incidents ? incidentItems.value : [],
    qaJobs: sourceAccess.value.translation_qa ? qaPreviewJobs.value : [],
    jobItems: sourceAccess.value.jobs ? jobPreviewJobs.value : [],
    limit: 10,
  }),
);
const previewFilterTabs = computed(() => {
  const tabs: Array<{ id: PreviewFilterId; label: string; count: number }> = [
    { id: "all", label: "全部", count: previewRows.value.length },
  ];
  if (sourceAccess.value.incidents) {
    tabs.push({
      id: "incident",
      label: "异常",
      count: previewRows.value.filter((row) => row.source === "incident").length,
    });
  }
  if (sourceAccess.value.translation_qa) {
    tabs.push({
      id: "translation_qa",
      label: "翻译 QA",
      count: previewRows.value.filter((row) => row.source === "translation_qa").length,
    });
  }
  if (sourceAccess.value.jobs) {
    tabs.push({
      id: "job",
      label: "运行中/失败",
      count: previewRows.value.filter((row) => row.source === "job").length,
    });
  }
  return tabs;
});
const filteredPreviewRows = computed(() => {
  if (activePreviewFilter.value === "all") {
    return previewRows.value;
  }
  return previewRows.value.filter((row) => row.source === activePreviewFilter.value);
});
const incidentItemByJobId = computed(() => new Map(incidentItems.value.map((item) => [item.job.id, item])));
const firstGateMessage = computed(() => {
  const gate = gateSummary.value?.release_gate;
  if (!gate) {
    return "";
  }
  const firstBlockerFinding = gate.blocker_findings?.[0]?.message;
  if (firstBlockerFinding) {
    return firstBlockerFinding;
  }
  if (gate.blockers.length) {
    return readinessCodeText(gate.blockers[0]);
  }
  const firstWarningFinding = gate.warning_findings?.[0]?.message;
  if (firstWarningFinding) {
    return firstWarningFinding;
  }
  if (gate.warnings.length) {
    return readinessCodeText(gate.warnings[0]);
  }
  return "";
});
const moduleErrorEntries = computed<ModuleErrorEntry[]>(() => {
  const entries: ModuleErrorEntry[] = [];
  if (incidentsState.error) {
    entries.push({ id: "incidents", label: "异常队列", error: incidentsState.error, retry: () => void loadIncidentsModule() });
  }
  if (qaState.error) {
    entries.push({ id: "translation_qa", label: "翻译 QA", error: qaState.error, retry: () => void loadQaModule() });
  }
  if (jobsState.error) {
    entries.push({ id: "jobs", label: "任务队列", error: jobsState.error, retry: () => void loadJobsModule() });
  }
  return entries;
});

onMounted(() => {
  void loadAll();
});

function goCreateJob(): void {
  void router.push("/jobs/new");
}

function openCockpitDiagnostic(jobId: string): void {
  const item = incidentItemByJobId.value.get(jobId);
  if (!item) {
    return;
  }
  void incidentDiagnostic.openDiagnostic(item);
}

async function handleCockpitIncidentRetry(item: DocumentJobIncidentQueueItemResponse): Promise<void> {
  if (!item.retryable) {
    return;
  }
  cockpitActionPending.value = { ...cockpitActionPending.value, [item.job.id]: "retry" };
  try {
    await documentJobsApi.retry(item.job.id, "cockpit diagnostic retry");
    ElMessage.success("已提交重试。");
    await Promise.all([incidentDiagnostic.refreshDiagnostic(), loadIncidentsModule(), loadJobsModule()]);
  } catch (caught) {
    ElMessage.error(normalizeApiError(caught).message);
  } finally {
    const next = { ...cockpitActionPending.value };
    delete next[item.job.id];
    cockpitActionPending.value = next;
  }
}

async function loadAll(): Promise<void> {
  if (!hasAccess.value) {
    return;
  }
  const loads: Promise<void>[] = [loadJobsModule(), loadQaModule(), loadIncidentsModule(), loadSavedViews()];
  if (canReadSettings.value) {
    loads.push(loadGateSummary());
  }
  await Promise.all(loads);
  lastLoadedAt.value = new Date().toISOString();
}

async function loadJobsModule(): Promise<void> {
  if (!sourceAccess.value.jobs) {
    return;
  }
  jobsState.loading = true;
  jobsState.error = null;
  try {
    const [summaryResponse, failedResponse, activeResponse] = await Promise.all([
      documentJobsApi.list({ page: 1, page_size: 1, sort: "updated_at_desc", include_archived: false }),
      documentJobsApi.list({ page: 1, page_size: 4, status: "failed", sort: "updated_at_desc", include_archived: false }),
      documentJobsApi.list({ page: 1, page_size: 4, status_group: "active", sort: "updated_at_asc", include_archived: false }),
    ]);
    jobSummary.value = summaryResponse.summary;
    jobPreviewJobs.value = [...failedResponse.items, ...activeResponse.items];
  } catch (caught) {
    jobsState.error = normalizeApiError(caught);
  } finally {
    jobsState.loading = false;
  }
}

async function loadQaModule(): Promise<void> {
  if (!sourceAccess.value.translation_qa) {
    return;
  }
  qaState.loading = true;
  qaState.error = null;
  try {
    const response = await documentJobsApi.list({
      page: 1,
      page_size: 8,
      translation_qa_status: "all",
      sort: "updated_at_desc",
      include_archived: false,
    });
    qaSummary.value = response.translation_qa_summary ?? {};
    qaPreviewJobs.value = response.items;
    syncTranslationQaBadgeCount(
      (qaSummary.value.blocked ?? 0) + (qaSummary.value.needs_fix ?? 0) + (qaSummary.value.unreviewed ?? 0),
    );
  } catch (caught) {
    qaState.error = normalizeApiError(caught);
  } finally {
    qaState.loading = false;
  }
}

async function loadIncidentsModule(): Promise<void> {
  if (!sourceAccess.value.incidents) {
    return;
  }
  incidentsState.loading = true;
  incidentsState.error = null;
  try {
    const response = await documentJobIncidentsApi.list({ page: 1, page_size: 6, sort: "priority" });
    incidentItems.value = response.items;
    incidentSummary.value = response.summary;
    syncIncidentsBadgeCount(
      response.summary.total ?? ((response.summary.retryable || 0) + (response.summary.stalled || 0)),
    );
  } catch (caught) {
    incidentsState.error = normalizeApiError(caught);
  } finally {
    incidentsState.loading = false;
  }
}

async function loadGateSummary(): Promise<void> {
  if (!canReadSettings.value) {
    return;
  }
  gateState.loading = true;
  gateState.error = null;
  try {
    gateSummary.value = await configSummaryApi.get("overview");
  } catch (caught) {
    gateState.error = normalizeApiError(caught);
  } finally {
    gateState.loading = false;
  }
}

async function loadSavedViews(): Promise<void> {
  const pageKeys = accessiblePageKeys.value;
  if (!pageKeys.length) {
    return;
  }
  savedViewsState.loading = true;
  savedViewsState.error = null;
  const nextErrors: Partial<Record<SavedViewPageKey, ApiClientError>> = {};
  await Promise.all(
    pageKeys.map(async (pageKey) => {
      try {
        const response = await savedViewsApi.list(pageKey);
        savedViewsByPage.value = {
          ...savedViewsByPage.value,
          [pageKey]: response.items,
        };
      } catch (caught) {
        nextErrors[pageKey] = normalizeApiError(caught);
        savedViewsByPage.value = {
          ...savedViewsByPage.value,
          [pageKey]: [],
        };
      }
    }),
  );
  savedViewErrors.value = nextErrors;
  savedViewsState.error = Object.values(nextErrors)[0] ?? null;
  savedViewsState.loading = false;
}

function countText(count: number | null): string {
  return count === null ? "..." : String(count);
}

function pageLabel(pageKey: SavedViewPageKey): string {
  return COCKPIT_PAGE_LABELS[pageKey];
}

function statusText(row: OperationsPreviewRow): string {
  if (row.source === "incident") {
    return incidentFailureTypeText[row.status as keyof typeof incidentFailureTypeText] || row.status;
  }
  if (row.source === "translation_qa") {
    return translationQaStatusText[row.status as TranslationQaStatus] || row.status;
  }
  return jobStatusText[row.status as keyof typeof jobStatusText] || row.status;
}
</script>

<style scoped lang="scss">
.operations-cockpit-page {
  display: grid;
  align-content: start;
  grid-auto-rows: max-content;
  gap: var(--app-space-3);
}

.cockpit-command-header,
.cockpit-panel,
.cockpit-empty-panel {
  min-width: 0;
  border: 1px solid var(--app-color-border);
  border-radius: var(--app-radius-md);
  background: var(--app-color-surface);
  box-shadow: var(--app-shadow-subtle);
}

.cockpit-command-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--app-space-4);
  padding: var(--app-space-4);
}

.sync-pill {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-height: 32px;
  padding: 0 var(--app-space-3);
  border: 1px solid var(--app-color-border-soft);
  border-radius: var(--app-radius-pill);
  background: var(--app-color-surface-muted);
  color: var(--app-color-text-muted);
  font-size: 12px;
}

.sync-pill > span {
  width: 8px;
  height: 8px;
  border-radius: var(--app-radius-pill);
  background: var(--app-color-success);
}

.sync-pill.is-loading > span {
  background: var(--app-color-info);
  animation: app-status-pulse var(--app-motion-slow) ease-out infinite alternate;
}

.priority-strip {
  overflow-x: auto;
  display: grid;
  grid-auto-columns: minmax(160px, 1fr);
  grid-auto-flow: column;
  gap: var(--app-space-2);
  width: 100%;
  max-width: 100%;
  min-width: 0;
  padding-bottom: 2px;
}

.priority-item {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  align-items: center;
  gap: var(--app-space-2);
  min-width: 0;
  min-height: 72px;
  padding: var(--app-space-3);
  border: 1px solid var(--app-color-border);
  border-radius: var(--app-radius-md);
  background: var(--app-color-surface);
  color: var(--app-color-text);
  box-shadow: var(--app-shadow-subtle);
}

.priority-item:hover,
.priority-item:focus-visible {
  border-color: var(--app-color-primary-border);
  color: var(--app-color-primary-hover);
}

.priority-count {
  display: grid;
  min-width: 42px;
  min-height: 42px;
  place-items: center;
  border-radius: var(--app-radius-md);
  background: var(--app-color-surface-muted);
  font-family: var(--app-font-mono);
  font-size: 18px;
  font-weight: 760;
}

.priority-item.is-danger .priority-count {
  background: var(--app-color-danger-soft);
  color: var(--app-color-danger);
}

.priority-item.is-warning .priority-count {
  background: var(--app-color-warning-soft);
  color: var(--app-color-warning);
}

.priority-item.is-info .priority-count {
  background: var(--app-color-info-soft);
  color: var(--app-color-info);
}

.priority-item.is-success .priority-count {
  background: var(--app-color-success-soft);
  color: var(--app-color-success);
}

.priority-copy {
  display: grid;
  gap: 2px;
  min-width: 0;
}

.priority-copy strong,
.priority-copy small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.priority-copy strong {
  font-size: 14px;
}

.priority-copy small {
  color: var(--app-color-text-muted);
  font-size: 12px;
}

.cockpit-main-grid {
  display: grid;
  grid-template-columns: minmax(0, 2fr) minmax(300px, 1fr);
  grid-template-areas: "queue rail";
  align-items: start;
  gap: var(--app-space-3);
  min-width: 0;
}

.cockpit-queue-column {
  grid-area: queue;
  min-width: 0;
}

.cockpit-rail-column {
  grid-area: rail;
  display: grid;
  gap: var(--app-space-3);
  min-width: 0;
}

.cockpit-panel,
.cockpit-empty-panel {
  padding: var(--app-space-4);
}

.cockpit-empty-panel {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--app-space-3);
}

.cockpit-empty-panel h2,
.compact-empty strong {
  margin: 0;
  font-size: 18px;
}

.cockpit-empty-panel p {
  margin: var(--app-space-1) 0 0;
  color: var(--app-color-text-muted);
}

.panel-link,
.row-action {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 30px;
  padding: 0 var(--app-space-3);
  border: 1px solid var(--app-color-primary-border);
  border-radius: var(--app-radius-md);
  background: var(--app-color-primary-soft);
  color: var(--app-color-primary-hover);
  font-size: 13px;
  font-weight: 700;
  white-space: nowrap;
}

.section-header.compact {
  margin-bottom: var(--app-space-3);
}

.preview-filter-strip {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: var(--app-space-3);
}

.preview-filter-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 11px;
  border: 1px solid var(--app-color-border);
  border-radius: var(--app-radius-pill);
  background: var(--app-color-surface-muted);
  color: var(--app-color-text-muted);
  font: inherit;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: border-color var(--app-motion-fast) ease, background-color var(--app-motion-fast) ease, color var(--app-motion-fast) ease;
}

.preview-filter-chip small {
  font-family: var(--app-font-mono);
  font-size: 11px;
}

.preview-filter-chip.is-active {
  border-color: var(--app-color-primary-border);
  background: var(--app-color-primary-soft);
  color: var(--app-color-primary-hover);
}

.preview-filter-chip:focus-visible {
  outline: 2px solid var(--app-color-primary);
  outline-offset: 2px;
}

.saved-view-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: var(--app-space-2);
  width: 100%;
  min-width: 0;
}

.saved-view-entry {
  display: grid;
  gap: 3px;
  min-width: 0;
  min-height: 62px;
  padding: var(--app-space-3);
  border: 1px solid var(--app-color-border-soft);
  border-radius: var(--app-radius-md);
  background: var(--app-color-surface-muted);
  color: var(--app-color-text);
}

.saved-view-entry:hover,
.saved-view-entry:focus-visible {
  border-color: var(--app-color-primary-border);
  color: var(--app-color-primary-hover);
}

.saved-view-entry span,
.saved-view-entry small {
  color: var(--app-color-text-muted);
  font-size: 12px;
}

.saved-view-entry strong {
  overflow: hidden;
  font-size: 14px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.gate-mini-body,
.gate-mini-error {
  display: grid;
  gap: var(--app-space-2);
}

.gate-mini-status-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.gate-mini-counts {
  color: var(--app-color-text-muted);
  font-size: 12px;
  font-weight: 600;
}

.gate-mini-hint,
.gate-mini-error span {
  margin: 0;
  color: var(--app-color-text-muted);
  font-size: 12px;
  line-height: 1.5;
  overflow-wrap: anywhere;
}

.gate-mini-link {
  color: var(--app-color-primary-hover);
  font-size: 13px;
  font-weight: 600;
  text-decoration: none;
}

.gate-mini-link:hover {
  text-decoration: underline;
}

.module-error-list {
  display: grid;
  gap: var(--app-space-2);
  margin-top: var(--app-space-3);
}

.module-error {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--app-space-2);
  min-width: 0;
  padding: var(--app-space-2) var(--app-space-3);
  border: 1px solid var(--app-color-danger-border);
  border-radius: var(--app-radius-md);
  background: var(--app-color-danger-soft);
  color: var(--app-color-danger);
  font-size: 13px;
}

.module-error span {
  min-width: 0;
  overflow-wrap: anywhere;
}

.module-refresh-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: var(--app-space-1);
}

.compact-loading,
.compact-empty {
  display: grid;
  gap: var(--app-space-1);
  min-height: 72px;
  place-items: center;
  border: 1px dashed var(--app-color-border);
  border-radius: var(--app-radius-md);
  background: var(--app-color-surface-muted);
  color: var(--app-color-text-muted);
  text-align: center;
}

.preview-table {
  overflow-x: auto;
  display: block;
  width: 100%;
  max-width: 100%;
  min-width: 0;
  border: 1px solid var(--app-color-border-soft);
  border-radius: var(--app-radius-md);
}

.preview-row {
  display: grid;
  grid-template-columns: minmax(210px, 1.55fr) minmax(96px, 0.65fr) minmax(136px, 0.85fr) minmax(150px, 1.1fr) minmax(126px, auto);
  align-items: center;
  gap: var(--app-space-2);
  min-width: 740px;
  min-height: 56px;
  padding: var(--app-space-2) var(--app-space-3);
  border-bottom: 1px solid var(--app-color-border-soft);
}

.preview-row:last-child {
  border-bottom: 0;
}

.preview-row-head {
  min-height: 40px;
  background: var(--app-color-surface-muted);
  color: var(--app-color-text-muted);
  font-size: 12px;
  font-weight: 760;
}

.preview-identity {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  grid-template-areas:
    "chip name"
    "chip id";
  gap: 2px var(--app-space-2);
  min-width: 0;
}

.preview-identity strong,
.preview-identity small,
.status-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.preview-identity strong {
  grid-area: name;
}

.preview-identity small {
  grid-area: id;
  color: var(--app-color-text-muted);
}

.preview-row-actions {
  display: inline-flex;
  align-items: center;
  justify-content: flex-end;
  gap: 4px;
}

.source-chip {
  grid-area: chip;
  align-self: center;
  min-width: 44px;
  padding: 3px 8px;
  border-radius: var(--app-radius-pill);
  background: var(--app-color-surface-muted);
  color: var(--app-color-text-muted);
  font-size: 12px;
  font-weight: 760;
  text-align: center;
}

.source-chip.is-danger {
  background: var(--app-color-danger-soft);
  color: var(--app-color-danger);
}

.source-chip.is-warning {
  background: var(--app-color-warning-soft);
  color: var(--app-color-warning);
}

.source-chip.is-info {
  background: var(--app-color-info-soft);
  color: var(--app-color-info);
}

.source-chip.is-success {
  background: var(--app-color-success-soft);
  color: var(--app-color-success);
}

@media (max-width: 1180px) {
  .cockpit-main-grid {
    grid-template-columns: 1fr;
    grid-template-areas:
      "rail"
      "queue";
  }

  .saved-view-grid {
    grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
  }
}

@media (max-width: 920px) {
  .cockpit-command-header,
  .cockpit-empty-panel,
  .section-header.compact {
    align-items: flex-start;
    flex-direction: column;
  }

  .module-refresh-actions {
    justify-content: flex-start;
  }

  .priority-strip {
    display: flex;
  }

  .priority-item {
    flex: 0 0 min(70vw, 220px);
  }

  .preview-table {
    overflow: visible;
  }

  .preview-row {
    min-width: 0;
    grid-template-columns: 1fr;
    gap: var(--app-space-1);
    align-items: start;
  }

  .preview-row-head {
    display: none;
  }

  .preview-row-actions {
    justify-content: flex-start;
  }
}

@media (max-width: 520px) {
  .operations-cockpit-page {
    gap: var(--app-space-2);
  }

  .cockpit-command-header,
  .cockpit-panel,
  .cockpit-empty-panel {
    padding: var(--app-space-3);
  }

  .priority-item {
    min-height: 66px;
  }

  .saved-view-grid {
    grid-template-columns: 1fr;
  }
}
</style>
