<!-- File: frontend/src/pages/AuditLogPage.vue -->
<!-- Purpose: Render the Admin-only audit event search, structured details display, current-page CSV export, and governed filtered export. -->
<template>
  <main class="audit-log-page app-page" aria-labelledby="audit-log-title">
    <WorkbenchPageHeader
      title-id="audit-log-title"
      kicker="Audit"
      title="审计日志"
      description="只读查询已记录的高风险成功操作。"
    >
      <template #actions>
        <div class="heading-actions">
        <el-button :icon="Download" :disabled="total === 0" :loading="exportingAll" @click="exportFilteredCsv">
          导出筛选结果
        </el-button>
        <el-button :icon="Download" :disabled="events.length === 0" @click="exportCurrentPageCsv">
          导出当前页
        </el-button>
        <el-button :icon="Refresh" :loading="loading" @click="loadEvents">刷新</el-button>
        </div>
      </template>
    </WorkbenchPageHeader>

    <ApiErrorAlert class="app-page-shell" :error="error" />

    <section class="app-page-shell" aria-label="审计日志筛选">
      <WorkbenchPanelCard
        title="筛选条件"
        subtitle="按 actor、action、target 和时间范围查询结构化审计事件。"
        card-class="filter-section app-filter-panel"
      >
      <el-form class="filter-form" label-position="top">
        <el-form-item label="搜索">
          <el-input
            v-model="filters.q"
            clearable
            placeholder="audit id / action / target / actor / trace / details"
            @keyup.enter="applyFilters"
          />
        </el-form-item>
        <el-form-item label="Actor role">
          <el-select v-model="filters.actor_role" clearable placeholder="全部角色">
            <el-option label="admin" value="admin" />
            <el-option label="operator" value="operator" />
            <el-option label="jobs" value="jobs" />
            <el-option label="anonymous" value="anonymous" />
          </el-select>
        </el-form-item>
        <el-form-item label="Action">
          <el-input v-model="filters.action" clearable placeholder="document_job.retry" @keyup.enter="applyFilters" />
        </el-form-item>
        <el-form-item label="Target type">
          <el-input v-model="filters.target_type" clearable placeholder="document_job" @keyup.enter="applyFilters" />
        </el-form-item>
        <el-form-item label="Target ID">
          <el-input v-model="filters.target_id" clearable placeholder="job_xxx" @keyup.enter="applyFilters" />
        </el-form-item>
        <el-form-item label="Actor ID">
          <el-input v-model="filters.actor_id" clearable placeholder="user_admin" @keyup.enter="applyFilters" />
        </el-form-item>
        <el-form-item label="时间范围" class="date-filter">
          <el-date-picker
            v-model="createdRange"
            type="datetimerange"
            start-placeholder="开始时间"
            end-placeholder="结束时间"
            unlink-panels
          />
        </el-form-item>
        <el-form-item label="排序">
          <el-select v-model="sort">
            <el-option label="最新优先" value="created_at_desc" />
            <el-option label="最早优先" value="created_at_asc" />
          </el-select>
        </el-form-item>
      </el-form>
      <div class="filter-actions">
        <el-button @click="resetFilters">重置</el-button>
        <el-button type="primary" @click="applyFilters">查询</el-button>
      </div>
      </WorkbenchPanelCard>
    </section>

    <section class="app-page-shell" aria-label="审计事件列表">
      <WorkbenchPanelCard
        title="事件列表"
        :subtitle="`共 ${total} 条${loadedAt ? ` · 更新于 ${formatDateTime(loadedAt)}` : ''}`"
        card-class="audit-table-section app-filter-panel app-table-card"
      >
        <template #actions>
          <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[25, 50, 100, 200]"
          layout="sizes, prev, pager, next"
          background
          small
          @current-change="loadEvents"
          @size-change="handlePageSizeChange"
        />
        </template>

        <el-table
        v-loading="loading"
        :data="events"
        empty-text="暂无审计事件"
        table-layout="fixed"
        class="audit-table"
      >
        <el-table-column prop="created_at" label="Created" min-width="180">
          <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column prop="action" label="Action" min-width="210">
          <template #default="{ row }">
            <span class="mono">{{ row.action }}</span>
          </template>
        </el-table-column>
        <el-table-column label="Actor" min-width="190">
          <template #default="{ row }">
            <el-tag size="small" effect="plain">{{ row.actor_role }}</el-tag>
            <span class="mono actor-id">{{ row.actor_id || "-" }}</span>
          </template>
        </el-table-column>
        <el-table-column label="Target" min-width="260">
          <template #default="{ row }">
            <div class="target-cell">
              <span class="mono">{{ row.target_type }}</span>
              <span class="mono muted">{{ row.target_id }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="reason" label="Reason" min-width="260" show-overflow-tooltip>
          <template #default="{ row }">{{ row.reason || "-" }}</template>
        </el-table-column>
        <el-table-column label="Details" min-width="140">
          <template #default="{ row }">
            <el-button
              v-if="hasAuditDetails(row)"
              :icon="View"
              size="small"
              type="primary"
              plain
              @click="openDetailsDrawer(row)"
            >
              查看 {{ auditDetailsKeyCount(row.details) }}
            </el-button>
            <span v-else class="muted">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="trace_id" label="Trace" min-width="180">
          <template #default="{ row }">
            <span class="mono">{{ row.trace_id }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="audit_id" label="Audit ID" min-width="180">
          <template #default="{ row }">
            <span class="mono">{{ row.audit_id }}</span>
          </template>
        </el-table-column>
        </el-table>
      </WorkbenchPanelCard>
    </section>

    <el-drawer v-model="detailsDrawer.visible" title="结构化审计详情" size="min(680px, 100vw)">
      <section v-if="detailsDrawer.event" class="details-drawer-content" aria-label="结构化审计详情">
        <el-descriptions :column="1" border size="small">
          <el-descriptions-item label="audit_id">
            <span class="mono">{{ detailsDrawer.event.audit_id }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="action">
            <span class="mono">{{ detailsDrawer.event.action }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="target">
            <span class="mono">{{ detailsDrawer.event.target_type }}:{{ detailsDrawer.event.target_id }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="created_at">
            {{ formatDateTime(detailsDrawer.event.created_at) }}
          </el-descriptions-item>
        </el-descriptions>

        <section class="details-section app-evidence-panel app-table-card" aria-label="审计详情顶层字段">
          <h2 class="details-section-title">Top-level fields</h2>
          <el-table :data="selectedDetailEntries" table-layout="fixed" empty-text="暂无 details 字段">
            <el-table-column prop="key" label="Key" min-width="180">
              <template #default="{ row }">
                <span class="mono">{{ row.key }}</span>
              </template>
            </el-table-column>
            <el-table-column label="Value" min-width="320">
              <template #default="{ row }">
                <pre class="details-value mono">{{ row.value }}</pre>
              </template>
            </el-table-column>
          </el-table>
        </section>

        <section class="details-section app-evidence-panel" aria-label="审计详情 JSON">
          <h2 class="details-section-title">JSON</h2>
          <pre class="details-json mono">{{ selectedDetailsJson }}</pre>
        </section>
      </section>
    </el-drawer>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import { Download, Refresh, View } from "@element-plus/icons-vue";

import { auditEventsApi } from "@/api/auditEvents";
import type {
  AuditActorRole,
  AuditDetails,
  AuditDetailsValue,
  AuditEventExportQuery,
  AuditEventListQuery,
  AuditEventResponse,
  AuditEventSort,
} from "@/api/types";
import ApiErrorAlert from "@/components/ApiErrorAlert.vue";
import WorkbenchPageHeader from "@/components/WorkbenchPageHeader.vue";
import WorkbenchPanelCard from "@/components/WorkbenchPanelCard.vue";
import { normalizeApiError, type ApiClientError } from "@/utils/errors";
import { formatDateTime } from "@/utils/format";

type AuditFilters = {
  q: string;
  actor_role: AuditActorRole | "";
  action: string;
  target_type: string;
  target_id: string;
  actor_id: string;
};

type AuditEventMutableQuery = {
  actor_role?: AuditActorRole;
  action?: string;
  target_type?: string;
  target_id?: string;
  actor_id?: string;
  q?: string;
  created_from?: string;
  created_to?: string;
};

type AuditEventFilterKey = "q" | "action" | "target_type" | "target_id" | "actor_id";

type AuditDetailEntry = {
  key: string;
  value: string;
};

type AuditDetailsDrawerState = {
  visible: boolean;
  event: AuditEventResponse | null;
};

const FILTERED_EXPORT_MAX_ROWS = 1000;

const filters = reactive<AuditFilters>({
  q: "",
  actor_role: "",
  action: "",
  target_type: "",
  target_id: "",
  actor_id: "",
});
const createdRange = ref<[Date, Date] | null>(null);
const sort = ref<AuditEventSort>("created_at_desc");
const events = ref<AuditEventResponse[]>([]);
const total = ref(0);
const page = ref(1);
const pageSize = ref(50);
const loading = ref(false);
const exportingAll = ref(false);
const error = ref<ApiClientError | null>(null);
const loadedAt = ref<string | null>(null);
const detailsDrawer = reactive<AuditDetailsDrawerState>({
  visible: false,
  event: null,
});

const queryParams = computed<AuditEventListQuery>(() => {
  const params: AuditEventListQuery = {
    page: page.value,
    page_size: pageSize.value,
    sort: sort.value,
  };
  applyCurrentFilters(params);
  return params;
});

const exportQueryParams = computed<AuditEventExportQuery>(() => {
  const params: AuditEventExportQuery = {
    sort: sort.value,
    max_rows: FILTERED_EXPORT_MAX_ROWS,
  };
  applyCurrentFilters(params);
  return params;
});

const selectedDetailEntries = computed<AuditDetailEntry[]>(() => {
  const details = detailsDrawer.event?.details;
  if (!details) {
    return [];
  }
  return Object.entries(details).map(([key, value]) => ({
    key,
    value: formatAuditDetailsValue(value),
  }));
});

const selectedDetailsJson = computed(() => {
  if (!detailsDrawer.event?.details) {
    return "-";
  }
  return stringifyStableJson(detailsDrawer.event.details, 2);
});

// 读取当前筛选条件下的审计事件页。
async function loadEvents(): Promise<void> {
  loading.value = true;
  error.value = null;
  try {
    const response = await auditEventsApi.list(queryParams.value);
    events.value = response.items;
    total.value = response.total;
    loadedAt.value = new Date().toISOString();
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    loading.value = false;
  }
}

// 应用筛选条件并回到第一页。
function applyFilters(): void {
  page.value = 1;
  void loadEvents();
}

// 重置所有筛选条件并重新读取第一页。
function resetFilters(): void {
  filters.q = "";
  filters.actor_role = "";
  filters.action = "";
  filters.target_type = "";
  filters.target_id = "";
  filters.actor_id = "";
  createdRange.value = null;
  sort.value = "created_at_desc";
  page.value = 1;
  void loadEvents();
}

// 变更页大小时回到第一页，避免当前页超出新分页范围。
function handlePageSizeChange(): void {
  page.value = 1;
  void loadEvents();
}

// 导出当前筛选条件下的后端受治理 CSV，不创建服务端临时文件。
async function exportFilteredCsv(): Promise<void> {
  exportingAll.value = true;
  error.value = null;
  try {
    const response = await auditEventsApi.exportCsv(exportQueryParams.value);
    downloadTextFile(buildExportFilename("audit-events-filtered"), response.csv_text);
    if (response.manifest.truncated) {
      ElMessage.warning(`已导出前 ${response.manifest.exported_count} 条，匹配总数 ${response.manifest.matched_count} 条。`);
    } else {
      ElMessage.success(`已导出 ${response.manifest.exported_count} 条审计事件。`);
    }
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    exportingAll.value = false;
  }
}

// 导出当前已加载页，不触发后端文件生成，并保留结构化 details JSON 列。
function exportCurrentPageCsv(): void {
  const header = [
    "created_at",
    "audit_id",
    "actor_role",
    "actor_id",
    "action",
    "target_type",
    "target_id",
    "reason",
    "details_json",
    "trace_id",
  ];
  const rows = events.value.map((event) => [
    event.created_at,
    event.audit_id,
    event.actor_role,
    event.actor_id || "",
    event.action,
    event.target_type,
    event.target_id,
    event.reason || "",
    stringifyAuditDetailsForCsv(event.details),
    event.trace_id,
  ]);
  const csv = [header, ...rows].map((row) => row.map(csvCell).join(",")).join("\n");
  downloadTextFile(`audit-events-page-${page.value}.csv`, `${csv}\n`);
}

// 打开单条审计事件的结构化 details 抽屉。
function openDetailsDrawer(event: AuditEventResponse): void {
  detailsDrawer.event = event;
  detailsDrawer.visible = true;
}

// 判断审计事件是否带有可展示的结构化 details。
function hasAuditDetails(event: AuditEventResponse): boolean {
  return auditDetailsKeyCount(event.details) > 0;
}

// 统计 details 顶层字段数量，用于表格入口展示。
function auditDetailsKeyCount(details: AuditDetails | null): number {
  if (!details) {
    return 0;
  }
  return Object.keys(details).length;
}

// 把 details 值格式化为抽屉中可读的短文本或 JSON 片段。
function formatAuditDetailsValue(value: AuditDetailsValue): string {
  if (isAuditDetailsRecord(value) || Array.isArray(value)) {
    return stringifyStableJson(value, 2);
  }
  if (value === null) {
    return "null";
  }
  return String(value);
}

// 把 details 编码为当前页 CSV 使用的稳定紧凑 JSON。
function stringifyAuditDetailsForCsv(details: AuditDetails | null): string {
  if (!details) {
    return "";
  }
  return stringifyStableJson(details);
}

// 用排序后的对象键生成稳定 JSON，和后端 details_json 的确定性保持一致。
function stringifyStableJson(value: AuditDetailsValue, space?: number): string {
  return JSON.stringify(sortAuditDetailsValue(value), null, space) ?? "";
}

// 递归排序 details 对象键，保留数组顺序和原始 JSON 标量。
function sortAuditDetailsValue(value: AuditDetailsValue): AuditDetailsValue {
  if (Array.isArray(value)) {
    return value.map((item) => sortAuditDetailsValue(item));
  }
  if (isAuditDetailsRecord(value)) {
    return Object.fromEntries(
      Object.entries(value)
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([key, item]) => [key, sortAuditDetailsValue(item)]),
    );
  }
  return value;
}

// 判断 details 值是否是普通 JSON 对象。
function isAuditDetailsRecord(value: AuditDetailsValue): value is Record<string, AuditDetailsValue> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

// 把页面当前筛选条件同步到列表查询或导出查询参数。
function applyCurrentFilters(params: AuditEventMutableQuery): void {
  addTrimmedParam(params, "q", filters.q);
  addTrimmedParam(params, "action", filters.action);
  addTrimmedParam(params, "target_type", filters.target_type);
  addTrimmedParam(params, "target_id", filters.target_id);
  addTrimmedParam(params, "actor_id", filters.actor_id);
  if (filters.actor_role) {
    params.actor_role = filters.actor_role;
  }
  if (createdRange.value) {
    params.created_from = createdRange.value[0].toISOString();
    params.created_to = createdRange.value[1].toISOString();
  }
}

// 给可选字符串参数做统一 trim，空字符串不发送到后端。
function addTrimmedParam(params: AuditEventMutableQuery, key: AuditEventFilterKey, value: string): void {
  const normalized = value.trim();
  if (normalized) {
    Object.assign(params, { [key]: normalized });
  }
}

// 转义 CSV 单元格，避免逗号、换行和引号破坏文件结构。
function csvCell(value: string): string {
  return `"${value.replace(/"/g, "\"\"")}"`;
}

// 在浏览器侧下载文本文件，避免服务端生成临时导出文件。
function downloadTextFile(filename: string, content: string): void {
  const blob = new Blob([content], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

// 生成含时间戳的浏览器下载文件名。
function buildExportFilename(prefix: string): string {
  const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
  return `${prefix}-${timestamp}.csv`;
}

onMounted(() => {
  void loadEvents();
});
</script>

<style scoped lang="scss">
.audit-log-page {
  display: grid;
  gap: var(--app-space-4);
}

.page-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--app-space-4);
}

.heading-actions,
.filter-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--app-space-2);
}

.filter-form {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--app-space-3);
}

.filter-form :deep(.el-form-item) {
  margin-bottom: 0;
}

.date-filter {
  grid-column: span 2;
}

.filter-actions {
  justify-content: flex-end;
}

.section-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--app-space-4);
}

.audit-table {
  width: 100%;
}

.actor-id {
  display: inline-block;
  margin-left: 8px;
}

.target-cell {
  display: grid;
  gap: 4px;
  min-width: 0;
}

.target-cell span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.details-drawer-content {
  display: grid;
  gap: var(--app-space-4);
}

.details-section {
  display: grid;
  gap: var(--app-space-3);
}

.details-section-title {
  margin: 0;
  color: var(--app-color-text);
  font-size: 15px;
  line-height: 1.35;
}

.details-value,
.details-json {
  margin: 0;
  overflow: auto;
  border: 1px solid var(--app-color-border);
  border-radius: var(--app-radius-md);
  background: var(--app-color-surface);
  color: var(--app-color-text);
  font-size: 12px;
  line-height: 1.55;
  white-space: pre-wrap;
  word-break: break-word;
}

.details-value {
  max-height: 180px;
  padding: var(--app-space-2);
}

.details-json {
  max-height: 420px;
  padding: var(--app-space-3);
}

@media (max-width: 980px) {
  .filter-form {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .page-heading,
  .section-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .filter-form {
    grid-template-columns: 1fr;
  }

  .date-filter {
    grid-column: auto;
  }

  .filter-actions {
    justify-content: flex-start;
  }
}
</style>
