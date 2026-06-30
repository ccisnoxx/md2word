<!-- File: frontend/src/pages/OperationsCockpitPage.vue -->
<!-- Purpose: Personal operator cockpit that routes actionable work into existing queue pages. -->
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
      <section class="priority-strip app-page-shell app-page-shell--wide" aria-label="优先工作">
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

      <section class="app-page-shell app-page-shell--wide" aria-label="保存视图入口">
        <WorkbenchPanelCard
          title="个人入口"
          kicker="保存视图"
          card-class="cockpit-panel"
          header-class="compact"
        >
          <template #actions>
            <el-button size="small" :icon="Refresh" :loading="savedViewsState.loading" @click="loadSavedViews">刷新视图</el-button>
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

      <section class="app-page-shell app-page-shell--wide" aria-label="下一步工作">
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

          <div v-if="moduleErrorEntries.length" class="module-error-list" aria-label="队列加载错误">
            <div v-for="entry in moduleErrorEntries" :key="entry.id" class="module-error">
              <span>{{ entry.label }}加载失败：{{ entry.error.message }}</span>
              <el-button size="small" text @click="entry.retry">重试</el-button>
            </div>
          </div>

          <div v-if="previewLoading && !previewRows.length" class="compact-loading">工作队列加载中...</div>
          <div v-else-if="!previewRows.length" class="compact-empty">
            <strong>暂无待处理工作</strong>
            <span>可以通过上方保存视图进入现有页面继续巡检。</span>
          </div>
          <div v-else class="preview-table" role="table" aria-label="下一步工作列表">
            <div class="preview-row preview-row-head" role="row">
              <span>对象</span>
              <span>状态</span>
              <span>更新</span>
              <span>建议动作</span>
              <span>入口</span>
            </div>
            <div v-for="row in previewRows" :key="row.id" class="preview-row" role="row">
              <div class="preview-identity">
                <span class="source-chip" :class="`is-${row.tone}`">{{ row.sourceLabel }}</span>
                <strong>{{ row.jobName }}</strong>
                <small class="mono">{{ row.jobId }}</small>
              </div>
              <span class="status-text">{{ statusText(row) }}</span>
              <span>{{ formatDateTime(row.updatedAt) }}</span>
              <span>{{ row.suggestedAction }}</span>
              <RouterLink class="row-action" :to="row.to">打开</RouterLink>
            </div>
          </div>
        </WorkbenchPanelCard>
      </section>
    </template>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { Refresh } from "@element-plus/icons-vue";

import { documentJobIncidentsApi } from "@/api/documentJobIncidents";
import { documentJobsApi } from "@/api/documentJobs";
import { savedViewsApi } from "@/api/savedViews";
import WorkbenchPageHeader from "@/components/WorkbenchPageHeader.vue";
import WorkbenchPanelCard from "@/components/WorkbenchPanelCard.vue";
import type { DocumentJobIncidentSummaryResponse, DocumentJobResponse, SavedViewPageKey, SavedViewResponse, TranslationQaStatus } from "@/api/types";
import { getDefaultProtectedRoute, type AppAccessContext } from "@/navigation/appShell";
import { useAuthStore } from "@/stores/auth";
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

function createLoadState(): LoadState {
  return {
    loading: false,
    error: null,
  };
}

const auth = useAuthStore();
const jobsState = reactive(createLoadState());
const qaState = reactive(createLoadState());
const incidentsState = reactive(createLoadState());
const savedViewsState = reactive(createLoadState());
const jobSummary = ref<Record<string, number> | null>(null);
const qaSummary = ref<Partial<Record<TranslationQaStatus, number>> | null>(null);
const incidentSummary = ref<DocumentJobIncidentSummaryResponse | null>(null);
const jobPreviewJobs = ref<DocumentJobResponse[]>([]);
const qaPreviewJobs = ref<DocumentJobResponse[]>([]);
const incidentItems = ref<Awaited<ReturnType<typeof documentJobIncidentsApi.list>>["items"]>([]);
const savedViewsByPage = ref<Record<SavedViewPageKey, SavedViewResponse[]>>({
  jobs: [],
  translation_qa: [],
  incidents: [],
});
const savedViewErrors = ref<Partial<Record<SavedViewPageKey, ApiClientError>>>({});
const lastLoadedAt = ref<string | null>(null);

const access = computed<AppAccessContext>(() => ({
  role: auth.user?.role ?? null,
  roles: auth.user?.roles ?? [],
  permissions: auth.user?.permissions ?? [],
}));
const sourceAccess = computed<CockpitSourceAccess>(() => cockpitSourceAccess(access.value));
const hasAccess = computed(() => hasCockpitSourceAccess(sourceAccess.value));
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
    limit: 8,
  }),
);
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

async function loadAll(): Promise<void> {
  if (!hasAccess.value) {
    return;
  }
  await Promise.all([loadJobsModule(), loadQaModule(), loadIncidentsModule(), loadSavedViews()]);
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
  } catch (caught) {
    incidentsState.error = normalizeApiError(caught);
  } finally {
    incidentsState.loading = false;
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
  if (row.source === "translation_qa") {
    return translationQaStatusText[row.status as TranslationQaStatus] || row.status;
  }
  if (row.source === "incident") {
    return incidentFailureTypeText[row.status as keyof typeof incidentFailureTypeText] || row.status;
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

.command-copy,
.command-actions {
  min-width: 0;
}

.command-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  gap: var(--app-space-2);
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
  min-height: 32px;
  padding: 0 var(--app-space-3);
  border: 1px solid var(--app-color-primary-border);
  border-radius: var(--app-radius-md);
  background: var(--app-color-primary-soft);
  color: var(--app-color-primary-hover);
  font-weight: 700;
}

.section-header.compact {
  margin-bottom: var(--app-space-3);
}

.saved-view-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
  gap: var(--app-space-2);
  width: 100%;
  min-width: 0;
}

.saved-view-entry {
  display: grid;
  gap: 3px;
  min-width: 0;
  min-height: 68px;
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
  font-size: 15px;
  text-overflow: ellipsis;
  white-space: nowrap;
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
  grid-template-columns: minmax(260px, 1.7fr) minmax(110px, 0.7fr) minmax(160px, 0.9fr) minmax(200px, 1.2fr) minmax(72px, auto);
  align-items: center;
  gap: var(--app-space-3);
  min-width: 860px;
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

@media (max-width: 920px) {
  .cockpit-command-header,
  .cockpit-empty-panel,
  .section-header.compact {
    align-items: flex-start;
    flex-direction: column;
  }

  .command-actions,
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

  .row-action {
    width: fit-content;
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
