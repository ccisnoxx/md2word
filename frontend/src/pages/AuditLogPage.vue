<!-- File: frontend/src/pages/AuditLogPage.vue -->
<!-- Purpose: Render the Admin-only audit event search, table, current-page CSV export, and governed filtered export. -->
<template>
  <main class="audit-log-page" aria-labelledby="audit-log-title">
    <section class="page-heading">
      <div>
        <p class="page-kicker">Audit</p>
        <h1 id="audit-log-title">审计日志</h1>
        <p>只读查询已记录的高风险成功操作。</p>
      </div>
      <div class="heading-actions">
        <el-button :icon="Download" :disabled="total === 0" :loading="exportingAll" @click="exportFilteredCsv">
          导出筛选结果
        </el-button>
        <el-button :icon="Download" :disabled="events.length === 0" @click="exportCurrentPageCsv">
          导出当前页
        </el-button>
        <el-button :icon="Refresh" :loading="loading" @click="loadEvents">刷新</el-button>
      </div>
    </section>

    <ApiErrorAlert :error="error" />

    <section class="filter-section" aria-label="审计日志筛选">
      <el-form class="filter-form" label-position="top">
        <el-form-item label="搜索">
          <el-input
            v-model="filters.q"
            clearable
            placeholder="audit id / action / target / actor / trace"
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
    </section>

    <section class="audit-table-section" aria-label="审计事件列表">
      <div class="section-header">
        <div>
          <h2 class="section-title">事件列表</h2>
          <p class="section-subtitle">
            共 {{ total }} 条<span v-if="loadedAt"> · 更新于 {{ formatDateTime(loadedAt) }}</span>
          </p>
        </div>
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
      </div>

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
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import { Download, Refresh } from "@element-plus/icons-vue";

import { auditEventsApi } from "@/api/auditEvents";
import type { AuditActorRole, AuditEventExportQuery, AuditEventListQuery, AuditEventResponse, AuditEventSort } from "@/api/types";
import ApiErrorAlert from "@/components/ApiErrorAlert.vue";
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

// 导出当前已加载页，不触发后端文件生成。
function exportCurrentPageCsv(): void {
  const header = ["created_at", "audit_id", "actor_role", "actor_id", "action", "target_type", "target_id", "reason", "trace_id"];
  const rows = events.value.map((event) => [
    event.created_at,
    event.audit_id,
    event.actor_role,
    event.actor_id || "",
    event.action,
    event.target_type,
    event.target_id,
    event.reason || "",
    event.trace_id,
  ]);
  const csv = [header, ...rows].map((row) => row.map(csvCell).join(",")).join("\n");
  downloadTextFile(`audit-events-page-${page.value}.csv`, `${csv}\n`);
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
  gap: 18px;
}

.page-heading {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  padding: 10px 0 2px;
}

.page-kicker {
  margin: 0 0 4px;
  color: #2563eb;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0;
  text-transform: uppercase;
}

.page-heading h1 {
  margin: 0;
  color: #111827;
  font-size: 28px;
  line-height: 1.2;
}

.page-heading p:last-child {
  margin: 8px 0 0;
  color: #667085;
}

.heading-actions,
.filter-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.filter-section,
.audit-table-section {
  display: grid;
  gap: 12px;
  padding: 16px;
  border: 1px solid #d9e2ec;
  border-radius: 8px;
  background: #fff;
}

.filter-form {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px 12px;
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
  gap: 16px;
}

.section-title {
  margin: 0;
  color: #111827;
  font-size: 18px;
}

.section-subtitle {
  margin: 6px 0 0;
  color: #667085;
  font-size: 13px;
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

@media (prefers-color-scheme: dark) {
  .page-heading h1,
  .section-title {
    color: #f8fafc;
  }

  .filter-section,
  .audit-table-section {
    border-color: rgba(148, 163, 184, 0.22);
    background: rgba(15, 23, 42, 0.86);
  }
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
