<!-- File: frontend/src/pages/IncidentTriagePage.vue -->
<!-- Purpose: Render the lightweight document_job incident triage queue and diagnostic drawer. -->
<template>
  <main class="incident-page app-page" :class="{ 'has-bulk-actions': selectedItems.length }" aria-labelledby="incident-title">
    <section class="incident-command-header app-page-shell app-page-shell--wide">
      <div class="command-copy">
        <p class="page-kicker">异常分诊</p>
        <h1 id="incident-title" class="page-title">异常处理</h1>
        <p class="page-description">集中处理失败、阻塞、可重试和长时间未更新的 document_jobs。</p>
      </div>
      <div class="command-actions">
        <div class="live-pill" :class="{ 'is-loading': loading || backgroundRefreshing }">
          <span aria-hidden="true"></span>
          <strong>{{ syncStatusText }}</strong>
          <small v-if="lastRefreshedAt">{{ formatDateTime(lastRefreshedAt) }}</small>
        </div>
        <el-tooltip content="快捷键 R" placement="bottom">
          <el-button :icon="Refresh" :loading="loading" @click="manualRefresh">刷新</el-button>
        </el-tooltip>
      </div>
    </section>

    <section class="incident-summary-strip app-page-shell app-page-shell--wide" aria-label="异常队列汇总">
      <button type="button" class="summary-item is-warning" :class="{ 'is-active': stalledMinutesFilter === DEFAULT_STALLED_FILTER }" @click="applySummaryFilter('stalled')">
        <span>{{ summary?.stalled ?? 0 }}</span>
        <strong>停滞/超时</strong>
        <small>优先刷新状态</small>
      </button>
      <button type="button" class="summary-item is-danger" :class="{ 'is-active': statusFilter === 'failed' }" @click="applySummaryFilter('failed')">
        <span>{{ summary?.failed ?? 0 }}</span>
        <strong>失败任务</strong>
        <small>按可重试性分流</small>
      </button>
      <button type="button" class="summary-item is-info" :class="{ 'is-active': retryableFilter === 'true' }" @click="applySummaryFilter('retryable')">
        <span>{{ summary?.retryable ?? 0 }}</span>
        <strong>可直接重试</strong>
        <small>批量确认后执行</small>
      </button>
      <button type="button" class="summary-item is-danger" :class="{ 'is-active': failureTypeFilter === 'artifact_missing' }" @click="applySummaryFilter('artifact')">
        <span>{{ summary?.by_failure_type?.artifact_missing ?? 0 }}</span>
        <strong>产物缺失</strong>
        <small>先看证据</small>
      </button>
    </section>

    <SavedViewStrip
      class="app-page-shell app-page-shell--wide"
      :system-views="incidentSystemSavedViews"
      :personal-views="personalSavedViewItems"
      :active-view-id="activeSavedView"
      :loading="savedViewsLoading"
      @apply="applySavedView"
      @save-current="saveCurrentSavedView"
      @update="updateSavedViewFromCurrent"
      @rename="renameSavedView"
      @delete="deleteSavedView"
      @set-default="setDefaultSavedView"
      @move="moveSavedView"
    />

    <section class="incident-list-panel app-filter-panel app-page-shell app-page-shell--wide" aria-label="异常队列">
      <div class="section-header table-header">
        <div>
          <p class="table-kicker page-kicker">当前视图：{{ activeFilterLabel }}</p>
          <h2 class="section-title">异常队列</h2>
          <p class="section-subtitle">默认按处理优先级排序；抽屉状态通过 <span class="mono">incident_job_id</span> 恢复。</p>
        </div>
        <ShortcutHintList :items="incidentListShortcutHints" />
      </div>

      <div class="toolbar filter-toolbar">
        <el-input
          v-model="searchKeyword"
          class="search-input"
          clearable
          placeholder="搜索任务/文件/错误"
          :prefix-icon="Search"
          @clear="handleFilter"
          @keyup.enter="handleFilter"
        />
        <el-select v-model="statusFilter" clearable placeholder="全部状态" class="filter-select" @change="handleFilter">
          <el-option v-for="status in statuses" :key="status" :label="jobStatusText[status]" :value="status" />
        </el-select>
        <el-select v-model="stageFilter" clearable placeholder="阶段/失败阶段" class="filter-select" @change="handleFilter">
          <el-option v-for="stage in stages" :key="stage" :label="jobStageText[stage] || stage" :value="stage" />
        </el-select>
        <el-select v-model="failureTypeFilter" clearable placeholder="失败类型" class="filter-select" @change="handleFilter">
          <el-option v-for="failureType in incidentFailureTypes" :key="failureType" :label="incidentFailureTypeText[failureType]" :value="failureType" />
        </el-select>
        <el-select v-model="retryableFilter" placeholder="重试性" class="filter-select narrow" @change="handleFilter">
          <el-option label="全部" value="" />
          <el-option label="可重试" value="true" />
          <el-option label="不可重试" value="false" />
        </el-select>
        <el-popover placement="bottom-end" :width="420" trigger="click">
          <template #reference>
            <el-button :icon="Filter">
              更多筛选
              <span v-if="advancedFilterCount" class="filter-count">{{ advancedFilterCount }}</span>
            </el-button>
          </template>
          <div class="advanced-filter-panel">
            <label>
              <span>重试次数</span>
              <el-select v-model="retryCountFilter" clearable @change="handleFilter">
                <el-option v-for="bucket in incidentRetryCountBuckets" :key="bucket" :label="incidentRetryCountBucketText[bucket]" :value="bucket" />
              </el-select>
            </label>
            <label>
              <span>停滞分钟</span>
              <el-input-number v-model="stalledMinutesFilter" :min="1" :step="5" controls-position="right" @change="handleFilter" />
            </label>
            <label>
              <span>排序</span>
              <el-select v-model="sortFilter" @change="handleFilter">
                <el-option v-for="sort in incidentSortOptions" :key="sort" :label="incidentSortText[sort]" :value="sort" />
              </el-select>
            </label>
            <div class="advanced-filter-footer">
              <el-button text @click="resetAdvancedFilters">清空高级筛选</el-button>
            </div>
          </div>
        </el-popover>
        <el-button :icon="Refresh" :loading="loading" @click="handleFilter">搜索</el-button>
      </div>

      <div v-if="activeFilterChips.length" class="active-filter-chips" aria-label="当前筛选条件">
        <el-tag v-for="chip in activeFilterChips" :key="chip.key" closable effect="plain" @close="removeFilter(chip.key)">
          {{ chip.label }}
        </el-tag>
      </div>

      <ApiErrorAlert :error="error" :diagnostic-context="incidentErrorDiagnosticContext" />

      <BatchResultStrip
        v-if="normalizedBatchResult"
        v-model:expanded="batchResultExpanded"
        :result="normalizedBatchResult"
        @close="batchResult = null"
      >
        <template #actions>
          <el-button size="small" text :icon="Refresh" @click="manualRefresh">刷新队列</el-button>
          <el-button size="small" text :disabled="!failedBatchItems.length" @click="reselectFailedItems">重选失败/跳过</el-button>
        </template>
      </BatchResultStrip>

      <div class="incident-table-wrap">
        <el-table
          ref="tableRef"
          v-loading="loading"
          :data="items"
          border
          class="incident-table"
          empty-text="当前筛选下暂无异常"
          table-layout="fixed"
          :row-class-name="incidentRowClassName"
          @selection-change="handleSelectionChange"
          @row-click="openDiagnostic"
        >
          <el-table-column type="selection" width="44" />
          <el-table-column label="任务 / 证据" min-width="360">
            <template #default="{ row }">
              <div class="incident-main">
                <button type="button" class="job-title-button" @click.stop="openDiagnostic(row)">
                  {{ getJobSourceFilename(row.job) }}
                </button>
                <div class="job-meta">
                  <RouterLink class="mono job-id" :to="`/jobs/${row.job.id}`" @click.stop>{{ row.job.id }}</RouterLink>
                  <el-tag size="small" effect="plain">{{ incidentPriorityLabel(row) }}</el-tag>
                  <el-tag size="small" :type="failureTypeTagType(row)" effect="plain">
                    {{ failureTypeLabel(row) }}
                  </el-tag>
                </div>
                <div class="evidence-line">
                  <span>{{ row.suggested_action }}</span>
                  <small v-if="row.evidence_summary.length">{{ row.evidence_summary[0] }}</small>
                </div>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="150">
            <template #default="{ row }">
              <div class="status-cell">
                <JobStatusBadge :status="row.job.status" />
                <span>{{ stageLabel(row) }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="重试" width="150">
            <template #default="{ row }">
              <div class="retry-cell">
                <el-tag size="small" :type="row.retryable ? 'success' : 'info'" effect="plain">
                  {{ row.retryable ? "可重试" : "不可重试" }}
                </el-tag>
                <span>次数 {{ row.job.retry_count }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="更新" width="172">
            <template #default="{ row }">
              <div class="time-cell">
                <span>{{ formatDateTime(row.job.updated_at) }}</span>
                <small v-if="row.stalled_minutes !== null">停滞 {{ row.stalled_minutes }} 分钟</small>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="170" fixed="right">
            <template #default="{ row }">
              <div class="action-row">
                <el-button
                  size="small"
                  text
                  type="warning"
                  :disabled="!row.retryable || isActionBusy(row.job.id)"
                  :loading="actionPending[row.job.id] === 'retry'"
                  @click.stop="handleSingleRetry(row)"
                >
                  重试
                </el-button>
                <el-button size="small" text type="primary" @click.stop="openDiagnostic(row)">诊断</el-button>
                <el-button size="small" text @click.stop="openJobDetail(row)">详情</el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <div class="pagination-row">
        <el-pagination
          background
          layout="prev, pager, next, total"
          :current-page="page"
          :page-size="pageSize"
          :total="total"
          @current-change="handlePageChange"
        />
      </div>
    </section>

    <div v-if="selectedItems.length" class="bulk-action-bar" aria-label="批量异常操作">
      <div class="bulk-summary">
        <strong>已选 {{ selectedItems.length }} 个异常</strong>
        <span>可重试 {{ selectedRetryableCount }} · 将跳过 {{ selectedNonRetryableCount }}</span>
      </div>
      <div class="bulk-actions">
        <el-button type="warning" :loading="batchLoading" @click="handleBatchRetry">批量重试</el-button>
        <el-button :loading="batchLoading" @click="handleBatchRefresh">批量刷新</el-button>
        <el-button text @click="clearSelection">清除选择</el-button>
      </div>
    </div>

    <el-drawer
      :model-value="drawerVisible"
      class="incident-diagnostic-drawer"
      direction="rtl"
      :size="drawerSize"
      :with-header="false"
      :destroy-on-close="false"
      append-to-body
      @update:model-value="handleDrawerModelValue"
    >
      <section class="diagnostic-panel" aria-label="异常诊断">
        <header class="drawer-header">
          <div>
            <p class="page-kicker">异常诊断</p>
            <h2>{{ diagnosticTitle }}</h2>
            <p v-if="diagnostic?.item" class="drawer-subtitle">{{ diagnostic.item.suggested_action }}</p>
          </div>
          <el-button text @click="closeDiagnostic">关闭</el-button>
        </header>

        <ApiErrorAlert :error="drawerError" :diagnostic-context="drawerErrorDiagnosticContext" />
        <div v-if="drawerLoading" class="drawer-loading">诊断加载中...</div>
        <template v-else-if="diagnostic">
          <section class="diagnostic-summary">
            <div>
              <span>失败类型</span>
              <strong>{{ incidentFailureTypeText[diagnostic.item.failure_type] }}</strong>
            </div>
            <div>
              <span>重试性</span>
              <strong>{{ diagnostic.item.retryable ? "可重试" : diagnostic.item.retry_disabled_reason || "不可重试" }}</strong>
            </div>
            <div>
              <span>状态/阶段</span>
              <strong>{{ jobStatusText[diagnostic.item.job.status] }} / {{ stageLabel(diagnostic.item) }}</strong>
            </div>
            <div>
              <span>重试次数</span>
              <strong>{{ diagnostic.item.job.retry_count }}</strong>
            </div>
          </section>

          <section class="diagnostic-section">
            <h3>关键证据</h3>
            <dl class="evidence-list">
              <div>
                <dt>任务 ID</dt>
                <dd class="mono">{{ diagnostic.item.job.id }}</dd>
              </div>
              <div>
                <dt>文件</dt>
                <dd>{{ getJobSourceFilename(diagnostic.item.job) }}</dd>
              </div>
              <div>
                <dt>错误</dt>
                <dd>{{ diagnostic.item.job.error_code || "-" }} · {{ diagnostic.item.job.error_message || "-" }}</dd>
              </div>
              <div>
                <dt>时间</dt>
                <dd>创建 {{ formatDateTime(diagnostic.item.job.created_at) }} · 更新 {{ formatDateTime(diagnostic.item.job.updated_at) }}</dd>
              </div>
            </dl>
            <div class="evidence-chips">
              <el-tag v-for="entry in diagnostic.item.evidence_summary" :key="entry" effect="plain">{{ entry }}</el-tag>
            </div>
          </section>

          <section class="diagnostic-section">
            <h3>证据入口</h3>
            <div class="evidence-links">
              <RouterLink
                v-for="link in diagnostic.evidence_links"
                :key="link.kind"
                class="evidence-link"
                :class="{ 'is-disabled': !link.available }"
                :to="link.target"
              >
                <strong>{{ link.title }}</strong>
                <span>{{ link.helper || link.target }}</span>
              </RouterLink>
            </div>
          </section>

          <section class="diagnostic-section">
            <h3>最近事件</h3>
            <ol class="event-list">
              <li v-for="event in diagnostic.recent_events" :key="event.id">
                <span class="event-meta">{{ formatDateTime(event.created_at) }} · {{ event.level }} · {{ event.stage }}</span>
                <strong>{{ event.event_type }}</strong>
                <p>{{ event.message }}</p>
              </li>
            </ol>
          </section>

          <section class="diagnostic-section">
            <h3>文件摘要</h3>
            <div class="file-list">
              <div v-for="file in diagnostic.files" :key="file.file_id" class="file-row">
                <span class="mono">{{ file.file_id }}</span>
                <strong>{{ file.file_type || "-" }}</strong>
                <span>{{ file.status || "-" }}</span>
                <small>{{ file.original_filename || "-" }}</small>
              </div>
            </div>
          </section>
        </template>

        <footer class="drawer-footer">
          <ShortcutHintList :items="incidentDrawerShortcutHints" />
          <div class="drawer-actions">
            <el-button @click="refreshDiagnostic">刷新诊断</el-button>
            <el-button v-if="diagnostic?.item" @click="openJobDetail(diagnostic.item)">打开详情</el-button>
            <el-button
              v-if="diagnostic?.item"
              type="warning"
              :disabled="!diagnostic.item.retryable"
              :loading="actionPending[diagnostic.item.job.id] === 'retry'"
              @click="handleSingleRetry(diagnostic.item)"
            >
              重试
            </el-button>
          </div>
        </footer>
      </section>
    </el-drawer>
  </main>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { ElMessage, ElMessageBox, type TableInstance } from "element-plus";
import { Filter, Refresh, Search } from "@element-plus/icons-vue";
import { useRoute, useRouter, type LocationQuery } from "vue-router";

import { documentJobIncidentsApi } from "@/api/documentJobIncidents";
import { documentJobsApi } from "@/api/documentJobs";
import { savedViewsApi } from "@/api/savedViews";
import type {
  DocumentJobIncidentBulkResponse,
  DocumentJobIncidentDiagnosticResponse,
  DocumentJobIncidentFailureType,
  DocumentJobIncidentQueueItemResponse,
  DocumentJobIncidentRetryCountBucket,
  DocumentJobIncidentSort,
  DocumentJobIncidentSummaryResponse,
  DocumentJobStage,
  DocumentJobStatus,
  SavedViewResponse,
} from "@/api/types";
import ApiErrorAlert from "@/components/ApiErrorAlert.vue";
import BatchResultStrip from "@/components/BatchResultStrip.vue";
import JobStatusBadge from "@/components/JobStatusBadge.vue";
import SavedViewStrip from "@/components/SavedViewStrip.vue";
import ShortcutHintList from "@/components/ShortcutHintList.vue";
import { normalizeIncidentBatchResult } from "@/utils/batchResults";
import { formatDateTime, getJobSourceFilename, jobStageText, jobStatusText } from "@/utils/format";
import { normalizeApiError, type ApiClientError } from "@/utils/errors";
import type { ShortcutHint } from "@/utils/keyboardShortcuts";
import {
  countBatchRetryable,
  failedOrSkippedBatchItems,
  incidentFailureTagType,
  incidentFailureTypeText,
  incidentFailureTypes,
  incidentPriorityLabel,
  incidentRetryCountBucketText,
  incidentRetryCountBuckets,
  incidentSortOptions,
  incidentSortText,
  isDocumentJobIncidentStage,
  isDocumentJobIncidentStatus,
  isIncidentFailureType,
  isIncidentRetryCountBucket,
  isIncidentSort,
  shouldIgnoreIncidentShortcut,
} from "@/utils/incidents";
import {
  activeSavedViewId,
  hasMeaningfulSavedViewQuery,
  incidentsSavedViewStateToQuery,
  personalSavedViewToStripItem,
  systemSavedViews,
  type SavedViewState,
  type SavedViewStripItem,
} from "@/utils/savedViews";

const router = useRouter();
const route = useRoute();

const items = ref<DocumentJobIncidentQueueItemResponse[]>([]);
const savedViews = ref<SavedViewResponse[]>([]);
const savedViewsLoading = ref(false);
const loading = ref(false);
const backgroundRefreshing = ref(false);
const batchLoading = ref(false);
const error = ref<ApiClientError | null>(null);
const drawerError = ref<ApiClientError | null>(null);
const page = ref(1);
const pageSize = 20;
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
const activeJobId = ref("");
const selectedIncidentJobId = ref("");
const drawerVisible = ref(false);
const drawerLoading = ref(false);
const diagnostic = ref<DocumentJobIncidentDiagnosticResponse | null>(null);
const batchResult = ref<DocumentJobIncidentBulkResponse | null>(null);
const batchResultExpanded = ref(false);
const actionPending = ref<Record<string, "retry" | undefined>>({});
const lastRefreshedAt = ref<string | null>(null);
const tableRef = ref<TableInstance | null>(null);
const drawerSize = "min(760px, 94vw)";
const DEFAULT_STALLED_FILTER = 10;
const AUTO_REFRESH_MS = 12000;
let refreshTimer: number | undefined;
let routeSyncInProgress = false;
let drawerLoadToken = 0;

const statuses: DocumentJobStatus[] = ["pending", "queued", "running", "succeeded", "failed", "canceled"];
const stages: DocumentJobStage[] = ["uploaded", "parsing", "parsed", "ir_converting", "rendering", "uploading", "completed", "failed", "canceled"];
const incidentListShortcutHints: ShortcutHint[] = [
  { keys: ["R"], label: "刷新" },
  { keys: ["Esc"], label: "关闭抽屉" },
  { keys: ["J/K"], label: "移动" },
  { keys: ["Cmd/Ctrl", "Enter"], label: "安全动作" },
];
const incidentDrawerShortcutHints: ShortcutHint[] = [
  { keys: ["Esc"], label: "关闭" },
  { keys: ["Cmd/Ctrl", "Enter"], label: "安全重试" },
  { keys: ["J/K"], label: "上一条/下一条" },
];

type FilterChipKey = "status" | "stage" | "failure_type" | "retryable" | "retry_count" | "stalled_minutes" | "q" | "sort";
type SummaryFilter = "stalled" | "failed" | "retryable" | "artifact";

const incidentErrorDiagnosticContext = computed(() => ({
  route: route.fullPath,
  operation: "document_job_incidents.list",
}));
const drawerErrorDiagnosticContext = computed(() => ({
  route: route.fullPath,
  operation: "document_job_incidents.diagnostics",
  job_id: selectedIncidentJobId.value,
}));
const syncStatusText = computed(() => (loading.value || backgroundRefreshing.value ? "同步中" : "已同步"));
const activeFilterLabel = computed(() => {
  const statusText = statusFilter.value ? jobStatusText[statusFilter.value] : "全部状态";
  const failureText = failureTypeFilter.value ? incidentFailureTypeText[failureTypeFilter.value] : "全部失败类型";
  const retryText = retryableFilter.value === "true" ? "可重试" : retryableFilter.value === "false" ? "不可重试" : "全部重试性";
  return `${statusText} · ${failureText} · ${retryText}`;
});
const advancedFilterCount = computed(() => {
  let count = 0;
  if (retryCountFilter.value) {
    count += 1;
  }
  if (stalledMinutesFilter.value !== null) {
    count += 1;
  }
  if (sortFilter.value !== "priority") {
    count += 1;
  }
  return count;
});
const activeFilterChips = computed<Array<{ key: FilterChipKey; label: string }>>(() => {
  const chips: Array<{ key: FilterChipKey; label: string }> = [];
  if (statusFilter.value) {
    chips.push({ key: "status", label: `状态：${jobStatusText[statusFilter.value]}` });
  }
  if (stageFilter.value) {
    chips.push({ key: "stage", label: `阶段：${jobStageText[stageFilter.value] || stageFilter.value}` });
  }
  if (failureTypeFilter.value) {
    chips.push({ key: "failure_type", label: `类型：${incidentFailureTypeText[failureTypeFilter.value]}` });
  }
  if (retryableFilter.value) {
    chips.push({ key: "retryable", label: retryableFilter.value === "true" ? "可重试" : "不可重试" });
  }
  if (retryCountFilter.value) {
    chips.push({ key: "retry_count", label: `重试：${incidentRetryCountBucketText[retryCountFilter.value]}` });
  }
  if (stalledMinutesFilter.value !== null) {
    chips.push({ key: "stalled_minutes", label: `停滞 ≥ ${stalledMinutesFilter.value} 分钟` });
  }
  if (searchKeyword.value.trim()) {
    chips.push({ key: "q", label: `搜索：${searchKeyword.value.trim()}` });
  }
  if (sortFilter.value !== "priority") {
    chips.push({ key: "sort", label: `排序：${incidentSortText[sortFilter.value]}` });
  }
  return chips;
});
const incidentSystemSavedViews = systemSavedViews.incidents;
const personalSavedViewItems = computed(() => savedViews.value.map(personalSavedViewToStripItem));
const allSavedViewItems = computed(() => [...incidentSystemSavedViews, ...personalSavedViewItems.value]);
const currentSavedViewState = computed<SavedViewState>(() => {
  const filters: SavedViewState["filters"] = {};
  if (statusFilter.value) {
    filters.status = statusFilter.value;
  }
  if (stageFilter.value) {
    filters.stage = stageFilter.value;
  }
  if (failureTypeFilter.value) {
    filters.failure_type = failureTypeFilter.value;
  }
  if (retryableFilter.value) {
    filters.retryable = retryableFilter.value === "true";
  }
  if (retryCountFilter.value) {
    filters.retry_count = retryCountFilter.value;
  }
  if (stalledMinutesFilter.value !== null) {
    filters.stalled_minutes = stalledMinutesFilter.value;
  }
  if (searchKeyword.value.trim()) {
    filters.q = searchKeyword.value.trim();
  }
  return {
    filters,
    sort: sortFilter.value,
  };
});
const activeSavedView = computed(() => activeSavedViewId(currentSavedViewState.value, allSavedViewItems.value));
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
const diagnosticTitle = computed(() => diagnostic.value?.item.job.id || selectedIncidentJobId.value || "异常诊断");

async function loadIncidents(options: { background?: boolean; preserveError?: boolean } = {}): Promise<void> {
  if (loading.value || backgroundRefreshing.value) {
    return;
  }
  if (options.background) {
    backgroundRefreshing.value = true;
  } else {
    loading.value = true;
  }
  if (!options.preserveError) {
    error.value = null;
  }
  try {
    const response = await documentJobIncidentsApi.list({
      page: page.value,
      page_size: pageSize,
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
    if (options.background) {
      backgroundRefreshing.value = false;
    } else {
      loading.value = false;
    }
  }
}

async function loadSavedViews(): Promise<void> {
  savedViewsLoading.value = true;
  try {
    const response = await savedViewsApi.list("incidents");
    savedViews.value = response.items;
  } catch (caught) {
    handleSavedViewError(caught);
  } finally {
    savedViewsLoading.value = false;
  }
}

async function initializeSavedViewsAndLoad(): Promise<void> {
  applyRouteQueryFilters();
  syncDiagnosticFromRoute();
  await loadSavedViews();
  const defaultView = savedViews.value.find((view) => view.is_default);
  if (defaultView && !hasMeaningfulSavedViewQuery(route.query, "incidents")) {
    await applySavedView(personalSavedViewToStripItem(defaultView), true);
    return;
  }
  await syncRouteAndLoad(page.value, true);
}

async function applySavedView(view: SavedViewStripItem, replace = false): Promise<void> {
  batchResult.value = null;
  const query = incidentsSavedViewStateToQuery(view, 1, selectedIncidentJobId.value);
  await applySavedViewQuery(query, replace);
}

async function applySavedViewQuery(query: Record<string, string>, replace = false): Promise<void> {
  if (!isSameIncidentRouteQuery(route.query, query)) {
    routeSyncInProgress = true;
    try {
      await router[replace ? "replace" : "push"]({ name: "incidents", query });
    } finally {
      routeSyncInProgress = false;
    }
  }
  applyRouteQueryFilters();
  await loadIncidents();
}

async function promptSavedViewName(title: string, inputValue = ""): Promise<string | null> {
  try {
    const result = await ElMessageBox.prompt("名称仅用于当前页面的个人视图。", title, {
      inputValue,
      inputPlaceholder: "视图名称",
      confirmButtonText: "保存",
      cancelButtonText: "取消",
      inputValidator(value) {
        const normalized = value.trim();
        if (!normalized) {
          return "视图名称不能为空。";
        }
        if (normalized.length > 64) {
          return "视图名称最多 64 个字符。";
        }
        return true;
      },
    });
    return result.value.trim();
  } catch (caught) {
    if (caught === "cancel" || caught === "close") {
      return null;
    }
    throw caught;
  }
}

async function saveCurrentSavedView(): Promise<void> {
  const name = await promptSavedViewName("保存当前视图");
  if (!name) {
    return;
  }
  savedViewsLoading.value = true;
  try {
    await savedViewsApi.create({
      page_key: "incidents",
      name,
      filters: currentSavedViewState.value.filters,
      sort: currentSavedViewState.value.sort,
    });
    await loadSavedViews();
    ElMessage.success("视图已保存。");
  } catch (caught) {
    handleSavedViewError(caught);
  } finally {
    savedViewsLoading.value = false;
  }
}

async function updateSavedViewFromCurrent(view: SavedViewStripItem): Promise<void> {
  if (view.source !== "personal") {
    return;
  }
  try {
    await ElMessageBox.confirm(`将用当前筛选和排序覆盖“${view.name}”。`, "更新保存视图", {
      confirmButtonText: "确认更新",
      cancelButtonText: "返回",
      type: "warning",
    });
    savedViewsLoading.value = true;
    await savedViewsApi.update(view.id, {
      filters: currentSavedViewState.value.filters,
      sort: currentSavedViewState.value.sort,
    });
    await loadSavedViews();
    ElMessage.success("视图已更新。");
  } catch (caught) {
    if (caught === "cancel" || caught === "close") {
      return;
    }
    handleSavedViewError(caught);
  } finally {
    savedViewsLoading.value = false;
  }
}

async function renameSavedView(view: SavedViewStripItem): Promise<void> {
  if (view.source !== "personal") {
    return;
  }
  const name = await promptSavedViewName("重命名保存视图", view.name);
  if (!name || name === view.name) {
    return;
  }
  savedViewsLoading.value = true;
  try {
    await savedViewsApi.update(view.id, { name });
    await loadSavedViews();
    ElMessage.success("视图已重命名。");
  } catch (caught) {
    handleSavedViewError(caught);
  } finally {
    savedViewsLoading.value = false;
  }
}

async function deleteSavedView(view: SavedViewStripItem): Promise<void> {
  if (view.source !== "personal") {
    return;
  }
  try {
    await ElMessageBox.confirm(`删除后无法从该页面恢复“${view.name}”。`, "删除保存视图", {
      confirmButtonText: "确认删除",
      cancelButtonText: "返回",
      type: "warning",
    });
    savedViewsLoading.value = true;
    await savedViewsApi.delete(view.id);
    await loadSavedViews();
    ElMessage.success("视图已删除。");
  } catch (caught) {
    if (caught === "cancel" || caught === "close") {
      return;
    }
    handleSavedViewError(caught);
  } finally {
    savedViewsLoading.value = false;
  }
}

async function setDefaultSavedView(view: SavedViewStripItem): Promise<void> {
  if (view.source !== "personal") {
    return;
  }
  savedViewsLoading.value = true;
  try {
    await savedViewsApi.update(view.id, { is_default: true });
    await loadSavedViews();
    ElMessage.success("默认视图已更新。");
  } catch (caught) {
    handleSavedViewError(caught);
  } finally {
    savedViewsLoading.value = false;
  }
}

async function moveSavedView(view: SavedViewStripItem, direction: "left" | "right"): Promise<void> {
  if (view.source !== "personal") {
    return;
  }
  const ordered = [...savedViews.value].sort((left, right) => left.position - right.position);
  const index = ordered.findIndex((item) => item.view_id === view.id);
  const nextIndex = direction === "left" ? index - 1 : index + 1;
  if (index < 0 || nextIndex < 0 || nextIndex >= ordered.length) {
    return;
  }
  [ordered[index], ordered[nextIndex]] = [ordered[nextIndex], ordered[index]];
  savedViewsLoading.value = true;
  try {
    const response = await savedViewsApi.reorder({
      page_key: "incidents",
      view_ids: ordered.map((item) => item.view_id),
    });
    savedViews.value = response.items;
  } catch (caught) {
    handleSavedViewError(caught);
  } finally {
    savedViewsLoading.value = false;
  }
}

function handleSavedViewError(caught: unknown): void {
  const normalized = normalizeApiError(caught);
  error.value = normalized;
  ElMessage.error(normalized.message);
}

function firstQueryValue(value: unknown): string {
  if (Array.isArray(value)) {
    return typeof value[0] === "string" ? value[0] : "";
  }
  return typeof value === "string" ? value : "";
}

function positivePage(value: string): number {
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : 1;
}

function positiveNumber(value: string): number | null {
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}

function applyRouteQueryFilters(): void {
  const routeStatus = firstQueryValue(route.query.status);
  const routeStage = firstQueryValue(route.query.stage);
  const routeFailureType = firstQueryValue(route.query.failure_type);
  const routeRetryable = firstQueryValue(route.query.retryable);
  const routeRetryCount = firstQueryValue(route.query.retry_count);
  const routeSort = firstQueryValue(route.query.sort);
  const routePage = firstQueryValue(route.query.page);
  statusFilter.value = isDocumentJobIncidentStatus(routeStatus) ? routeStatus : "";
  stageFilter.value = isDocumentJobIncidentStage(routeStage) ? routeStage : "";
  failureTypeFilter.value = isIncidentFailureType(routeFailureType) ? routeFailureType : "";
  retryableFilter.value = routeRetryable === "true" || routeRetryable === "false" ? routeRetryable : "";
  retryCountFilter.value = isIncidentRetryCountBucket(routeRetryCount) ? routeRetryCount : "";
  stalledMinutesFilter.value = positiveNumber(firstQueryValue(route.query.stalled_minutes));
  searchKeyword.value = firstQueryValue(route.query.q);
  sortFilter.value = isIncidentSort(routeSort) ? routeSort : "priority";
  page.value = routePage ? positivePage(routePage) : 1;
}

function incidentRouteQuery(nextPage = page.value, incidentJobId: string | null = selectedIncidentJobId.value): Record<string, string> {
  const query: Record<string, string> = {
    page: String(nextPage),
    sort: sortFilter.value,
  };
  if (statusFilter.value) {
    query.status = statusFilter.value;
  }
  if (stageFilter.value) {
    query.stage = stageFilter.value;
  }
  if (failureTypeFilter.value) {
    query.failure_type = failureTypeFilter.value;
  }
  if (retryableFilter.value) {
    query.retryable = retryableFilter.value;
  }
  if (retryCountFilter.value) {
    query.retry_count = retryCountFilter.value;
  }
  if (stalledMinutesFilter.value !== null) {
    query.stalled_minutes = String(stalledMinutesFilter.value);
  }
  if (searchKeyword.value.trim()) {
    query.q = searchKeyword.value.trim();
  }
  if (incidentJobId) {
    query.incident_job_id = incidentJobId;
  }
  return query;
}

function isSameIncidentRouteQuery(candidate: LocationQuery, expected: Record<string, string>): boolean {
  const keys = ["status", "stage", "failure_type", "retryable", "retry_count", "stalled_minutes", "q", "sort", "page", "incident_job_id"];
  return keys.every((key) => firstQueryValue(candidate[key]) === (expected[key] ?? ""));
}

function isSameIncidentFilterRouteQuery(left: LocationQuery, right: LocationQuery): boolean {
  const keys = ["status", "stage", "failure_type", "retryable", "retry_count", "stalled_minutes", "q", "sort", "page"];
  return keys.every((key) => firstQueryValue(left[key]) === firstQueryValue(right[key]));
}

async function syncRouteAndLoad(nextPage: number, replace = false): Promise<void> {
  page.value = nextPage;
  const query = incidentRouteQuery(nextPage);
  if (!isSameIncidentRouteQuery(route.query, query)) {
    routeSyncInProgress = true;
    try {
      await router[replace ? "replace" : "push"]({ name: "incidents", query });
    } finally {
      routeSyncInProgress = false;
    }
  }
  await loadIncidents();
}

async function replaceIncidentJobQuery(jobId: string | null): Promise<void> {
  const query = incidentRouteQuery(page.value, jobId);
  if (isSameIncidentRouteQuery(route.query, query)) {
    return;
  }
  routeSyncInProgress = true;
  try {
    await router.replace({ name: "incidents", query });
  } finally {
    routeSyncInProgress = false;
  }
}

function handleFilter(): void {
  batchResult.value = null;
  void syncRouteAndLoad(1);
}

function handlePageChange(nextPage: number): void {
  void syncRouteAndLoad(nextPage);
}

function applySummaryFilter(kind: SummaryFilter): void {
  statusFilter.value = "";
  stageFilter.value = "";
  failureTypeFilter.value = "";
  retryableFilter.value = "";
  retryCountFilter.value = "";
  stalledMinutesFilter.value = null;
  searchKeyword.value = "";
  sortFilter.value = "priority";
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

function resetAdvancedFilters(): void {
  retryCountFilter.value = "";
  stalledMinutesFilter.value = null;
  sortFilter.value = "priority";
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

function clearSelection(): void {
  selectedItems.value = [];
  tableRef.value?.clearSelection();
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

function stageLabel(item: DocumentJobIncidentQueueItemResponse): string {
  const stage = item.job.failed_stage || item.job.stage;
  return jobStageText[stage] || stage;
}

function failureTypeLabel(item: DocumentJobIncidentQueueItemResponse): string {
  return incidentFailureTypeText[item.failure_type];
}

function failureTypeTagType(item: DocumentJobIncidentQueueItemResponse): "danger" | "warning" | "info" {
  return incidentFailureTagType(item.failure_type);
}

function incidentRowClassName({ row }: { row: DocumentJobIncidentQueueItemResponse }): string {
  return row.job.id === activeJobId.value ? "is-active-incident-row" : "";
}

async function manualRefresh(): Promise<void> {
  await loadIncidents();
  if (drawerVisible.value && selectedIncidentJobId.value) {
    await loadDiagnostics(selectedIncidentJobId.value);
  }
}

async function openDiagnostic(item: DocumentJobIncidentQueueItemResponse): Promise<void> {
  activeJobId.value = item.job.id;
  selectedIncidentJobId.value = item.job.id;
  drawerVisible.value = true;
  await replaceIncidentJobQuery(item.job.id);
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
  await replaceIncidentJobQuery(null);
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
    if (selectedIncidentJobId.value === item.job.id) {
      await loadDiagnostics(item.job.id);
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
  clearSelection();
  for (const item of items.value) {
    if (failedIds.has(item.job.id)) {
      tableRef.value?.toggleRowSelection(item, true);
    }
  }
}

function shouldAutoRefresh(): boolean {
  if (typeof document !== "undefined" && document.hidden) {
    return false;
  }
  return !drawerVisible.value && !batchLoading.value;
}

function startAutoRefresh(): void {
  refreshTimer = window.setInterval(() => {
    if (shouldAutoRefresh()) {
      void loadIncidents({ background: true, preserveError: true });
    }
  }, AUTO_REFRESH_MS);
}

function selectAdjacentIncident(delta: number): void {
  if (!items.value.length) {
    return;
  }
  const currentId = selectedIncidentJobId.value || activeJobId.value;
  const currentIndex = Math.max(0, items.value.findIndex((item) => item.job.id === currentId));
  const nextIndex = Math.min(Math.max(currentIndex + delta, 0), items.value.length - 1);
  const nextItem = items.value[nextIndex];
  activeJobId.value = nextItem.job.id;
  if (drawerVisible.value) {
    void openDiagnostic(nextItem);
  }
}

function handleIncidentKeydown(event: KeyboardEvent): void {
  if (shouldIgnoreIncidentShortcut(event.target)) {
    return;
  }
  if (event.key === "Escape" && drawerVisible.value) {
    event.preventDefault();
    void closeDiagnostic();
    return;
  }
  if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
    if (diagnostic.value?.item.retryable && !drawerLoading.value && !batchLoading.value) {
      event.preventDefault();
      void handleSingleRetry(diagnostic.value.item);
    }
    return;
  }
  if (event.metaKey || event.ctrlKey || event.altKey) {
    return;
  }
  const key = event.key.toLowerCase();
  if (key === "r") {
    event.preventDefault();
    void manualRefresh();
  } else if (key === "j") {
    event.preventDefault();
    selectAdjacentIncident(1);
  } else if (key === "k") {
    event.preventDefault();
    selectAdjacentIncident(-1);
  }
}

watch(
  () => route.query,
  (nextQuery, previousQuery) => {
    applyRouteQueryFilters();
    if (!routeSyncInProgress && !isSameIncidentFilterRouteQuery(nextQuery, previousQuery)) {
      void loadIncidents();
    }
    if (!routeSyncInProgress) {
      syncDiagnosticFromRoute();
    }
  },
);

onMounted(() => {
  window.addEventListener("keydown", handleIncidentKeydown);
  void initializeSavedViewsAndLoad();
  startAutoRefresh();
});

onBeforeUnmount(() => {
  window.removeEventListener("keydown", handleIncidentKeydown);
  if (refreshTimer !== undefined) {
    window.clearInterval(refreshTimer);
  }
});
</script>

<style scoped lang="scss">
.incident-page {
  position: relative;
  isolation: isolate;
  display: grid;
  align-content: start;
  grid-auto-rows: max-content;
  gap: var(--app-space-4);
  margin: -20px -24px -36px;
  padding: 28px 24px 42px;
  overflow: visible;
  color: var(--app-color-text);
  background: transparent;
}

.incident-command-header,
.incident-list-panel {
  position: relative;
}

.incident-command-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--app-space-4);
}

.command-copy {
  min-width: 0;
}

.command-actions,
.toolbar,
.bulk-actions,
.drawer-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--app-space-2);
}

.live-pill {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-height: 32px;
  padding: 6px 10px;
  border: 1px solid var(--app-color-border);
  border-radius: var(--app-radius-md);
  background: var(--app-color-surface);
  color: var(--app-color-text-muted);
}

.live-pill span {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: var(--el-color-success);
}

.live-pill.is-loading span {
  background: var(--el-color-warning);
}

.incident-summary-strip {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--app-space-3);
}

.summary-item {
  display: grid;
  grid-template-columns: auto 1fr;
  grid-template-areas:
    "count label"
    "count helper";
  gap: 2px 10px;
  min-width: 0;
  padding: 12px;
  border: 1px solid var(--app-color-border);
  border-radius: var(--app-radius-md);
  background: var(--app-color-surface);
  color: inherit;
  text-align: left;
  cursor: pointer;
}

.summary-item span {
  grid-area: count;
  font-size: 28px;
  font-weight: 700;
  line-height: 1;
}

.summary-item strong {
  grid-area: label;
}

.summary-item small {
  grid-area: helper;
  color: var(--app-color-text-muted);
}

.summary-item.is-active {
  border-color: var(--el-color-primary);
  box-shadow: 0 0 0 1px var(--el-color-primary-light-5);
}

.incident-list-panel {
  display: grid;
  gap: var(--app-space-3);
}

.section-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--app-space-4);
}

.filter-toolbar {
  align-items: stretch;
}

.search-input {
  width: min(320px, 100%);
}

.filter-select {
  width: 170px;
}

.filter-select.narrow {
  width: 128px;
}

.filter-count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 18px;
  height: 18px;
  margin-left: 4px;
  border-radius: 999px;
  background: var(--el-color-primary);
  color: #fff;
  font-size: 12px;
}

.advanced-filter-panel {
  display: grid;
  gap: var(--app-space-3);
}

.advanced-filter-panel label {
  display: grid;
  gap: 6px;
}

.advanced-filter-panel label > span {
  color: var(--app-color-text-muted);
  font-size: 12px;
}

.advanced-filter-footer {
  display: flex;
  justify-content: flex-end;
}

.active-filter-chips,
.job-meta,
.evidence-chips {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.incident-table-wrap {
  overflow-x: auto;
}

.incident-table {
  min-width: 980px;
}

.incident-main {
  display: grid;
  gap: 6px;
  min-width: 0;
}

.job-title-button {
  max-width: 100%;
  padding: 0;
  border: 0;
  overflow: hidden;
  background: transparent;
  color: var(--el-color-primary);
  font: inherit;
  font-weight: 650;
  text-align: left;
  text-overflow: ellipsis;
  white-space: nowrap;
  cursor: pointer;
}

.job-id {
  color: var(--app-color-text-muted);
}

.evidence-line {
  display: grid;
  gap: 2px;
  color: var(--app-color-text);
}

.evidence-line small {
  overflow: hidden;
  color: var(--app-color-text-muted);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.status-cell,
.retry-cell,
.time-cell {
  display: grid;
  gap: 6px;
  min-width: 0;
}

.time-cell small,
.retry-cell span,
.status-cell span {
  color: var(--app-color-text-muted);
  font-size: 12px;
}

.action-row {
  display: flex;
  align-items: center;
  gap: 4px;
}

.pagination-row {
  display: flex;
  justify-content: flex-end;
}

.bulk-action-bar {
  position: fixed;
  right: 24px;
  bottom: 20px;
  left: calc(var(--app-sidebar-width, 260px) + 24px);
  z-index: 20;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--app-space-3);
  padding: 12px 14px;
  border: 1px solid var(--app-color-border);
  border-radius: var(--app-radius-md);
  background: var(--app-color-surface);
  box-shadow: var(--app-shadow-lg);
}

.bulk-summary {
  display: grid;
  gap: 3px;
}

.bulk-summary span {
  color: var(--app-color-text-muted);
  font-size: 12px;
}

.diagnostic-panel {
  display: grid;
  grid-template-rows: auto 1fr auto;
  gap: var(--app-space-4);
  min-height: 100%;
  padding: 20px;
}

.drawer-header,
.drawer-footer {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--app-space-3);
}

.drawer-header h2 {
  margin: 0;
  font-size: 22px;
}

.drawer-subtitle {
  margin: 4px 0 0;
  color: var(--app-color-text-muted);
}

.drawer-loading {
  color: var(--app-color-text-muted);
}

.diagnostic-summary {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--app-space-2);
}

.diagnostic-summary div,
.diagnostic-section {
  min-width: 0;
  padding: 12px;
  border: 1px solid var(--app-color-border);
  border-radius: var(--app-radius-md);
  background: var(--app-color-surface);
}

.diagnostic-summary span {
  display: block;
  color: var(--app-color-text-muted);
  font-size: 12px;
}

.diagnostic-summary strong {
  display: block;
  margin-top: 4px;
  overflow-wrap: anywhere;
}

.diagnostic-section {
  display: grid;
  gap: var(--app-space-2);
}

.diagnostic-section h3 {
  margin: 0;
  font-size: 15px;
}

.evidence-list {
  display: grid;
  gap: 8px;
  margin: 0;
}

.evidence-list div {
  display: grid;
  grid-template-columns: 96px minmax(0, 1fr);
  gap: 10px;
}

.evidence-list dt {
  color: var(--app-color-text-muted);
}

.evidence-list dd {
  min-width: 0;
  margin: 0;
  overflow-wrap: anywhere;
}

.evidence-links {
  display: grid;
  gap: 8px;
}

.evidence-link {
  display: grid;
  gap: 2px;
  padding: 10px;
  border: 1px solid var(--app-color-border);
  border-radius: var(--app-radius-sm);
  color: inherit;
  text-decoration: none;
}

.evidence-link span {
  color: var(--app-color-text-muted);
  font-size: 12px;
}

.evidence-link.is-disabled {
  opacity: 0.55;
}

.event-list {
  display: grid;
  gap: 10px;
  padding-left: 18px;
  margin: 0;
}

.event-list p {
  margin: 2px 0 0;
}

.event-meta {
  display: block;
  color: var(--app-color-text-muted);
  font-size: 12px;
}

.file-list {
  display: grid;
  gap: 6px;
}

.file-row {
  display: grid;
  grid-template-columns: minmax(150px, 1fr) 110px 92px minmax(0, 1fr);
  gap: 8px;
  align-items: center;
  padding: 8px;
  border: 1px solid var(--app-color-border);
  border-radius: var(--app-radius-sm);
}

.file-row small {
  overflow: hidden;
  color: var(--app-color-text-muted);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}

:global(.incident-table .is-active-incident-row > td) {
  background: var(--el-color-primary-light-9) !important;
}

:global(.incident-diagnostic-drawer.el-drawer) {
  max-width: 100vw;
}

:global(.incident-diagnostic-drawer .el-drawer__body) {
  padding: 0;
}

@media (max-width: 900px) {
  .incident-page {
    margin: -16px -16px -28px;
    padding: 20px 16px 88px;
  }

  .incident-command-header,
  .section-header,
  .drawer-header,
  .drawer-footer,
  .bulk-action-bar {
    align-items: stretch;
    flex-direction: column;
  }

  .incident-summary-strip,
  .diagnostic-summary {
    grid-template-columns: 1fr 1fr;
  }

  .filter-toolbar > * {
    width: 100% !important;
  }

  .bulk-action-bar {
    right: 12px;
    left: 12px;
    bottom: 12px;
  }

  .file-row,
  .evidence-list div {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 520px) {
  .incident-summary-strip,
  .diagnostic-summary {
    grid-template-columns: 1fr;
  }
}
</style>
