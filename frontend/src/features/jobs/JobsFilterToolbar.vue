<template>
  <div class="toolbar primary-toolbar">
    <el-input
      v-model="searchKeyword"
      class="search-input"
      clearable
      placeholder="搜索任务/文件/错误"
      :prefix-icon="Search"
      @clear="handleFilter"
      @keyup.enter="handleFilter"
    />
    <el-select v-model="statusFilter" clearable placeholder="全部状态" class="filter-select" @change="handleStatusFilterChange">
      <el-option v-for="status in statuses" :key="status" :label="jobStatusText[status]" :value="status" />
    </el-select>
    <el-select v-model="qaStatusFilter" clearable placeholder="全部 QA" class="filter-select" @change="handleFilter">
      <el-option
        v-for="status in qaStatuses"
        :key="status"
        :label="translationQaStatusText[status]"
        :value="status"
      />
    </el-select>
    <el-popover placement="bottom-end" :width="430" trigger="click">
      <template #reference>
        <el-button :icon="Filter">
          更多筛选
          <span v-if="advancedFilterCount" class="filter-count">{{ advancedFilterCount }}</span>
        </el-button>
      </template>
      <div class="advanced-filter-panel">
        <label>
          <span>排序</span>
          <el-select v-model="sortFilter" @change="handleFilter">
            <el-option v-for="option in sortOptions" :key="option.value" :label="option.label" :value="option.value" />
          </el-select>
        </label>
        <label>
          <span>创建时间</span>
          <el-date-picker
            v-model="createdRange"
            type="datetimerange"
            start-placeholder="创建开始"
            end-placeholder="创建结束"
            value-format="YYYY-MM-DDTHH:mm:ssZ"
            @change="handleFilter"
          />
        </label>
        <div class="advanced-filter-footer">
          <el-switch v-model="includeArchived" active-text="含归档" inactive-text="默认" @change="handleFilter" />
          <el-button text @click="resetAdvancedFilters">清空高级筛选</el-button>
        </div>
      </div>
    </el-popover>
    <el-button :icon="Refresh" :loading="loading" @click="handleFilter">搜索</el-button>
    <WorkbenchTableSettings
      :model-value="tablePreferences"
      settings-id="jobs-table-settings"
      :columns="jobsTableColumns"
      @update:model-value="handleTablePreferencesUpdate"
      @reset="handleTablePreferencesReset"
    />
  </div>
</template>

<script setup lang="ts">
import type { UnwrapRef } from "vue";
import { Filter, Refresh, Search } from "@element-plus/icons-vue";
import WorkbenchTableSettings from "@/components/WorkbenchTableSettings.vue";
import { jobStatusText, translationQaStatusText } from "@/utils/format";
import { qaStatuses, sortOptions, statuses } from "./jobsListQuery";
import type { JobsList } from "./useJobsList";

const searchKeyword = defineModel<UnwrapRef<JobsList["searchKeyword"]>>("searchKeyword", { required: true });
const statusFilter = defineModel<UnwrapRef<JobsList["statusFilter"]>>("statusFilter", { required: true });
const qaStatusFilter = defineModel<UnwrapRef<JobsList["qaStatusFilter"]>>("qaStatusFilter", { required: true });
const sortFilter = defineModel<UnwrapRef<JobsList["sortFilter"]>>("sortFilter", { required: true });
const createdRange = defineModel<UnwrapRef<JobsList["createdRange"]>>("createdRange", { required: true });
const includeArchived = defineModel<UnwrapRef<JobsList["includeArchived"]>>("includeArchived", { required: true });
const {
  loading,
  advancedFilterCount,
  tablePreferences,
  jobsTableColumns,
  handleFilter,
  handleStatusFilterChange,
  resetAdvancedFilters,
  handleTablePreferencesUpdate,
  handleTablePreferencesReset,
} = defineProps<{
  loading: UnwrapRef<JobsList["loading"]>;
  advancedFilterCount: UnwrapRef<JobsList["advancedFilterCount"]>;
  tablePreferences: UnwrapRef<JobsList["tablePreferences"]>;
  jobsTableColumns: JobsList["jobsTableColumns"];
  handleFilter: JobsList["handleFilter"];
  handleStatusFilterChange: JobsList["handleStatusFilterChange"];
  resetAdvancedFilters: JobsList["resetAdvancedFilters"];
  handleTablePreferencesUpdate: JobsList["handleTablePreferencesUpdate"];
  handleTablePreferencesReset: JobsList["handleTablePreferencesReset"];
}>();
</script>

<style scoped lang="scss">
.primary-toolbar {
  justify-content: flex-end;
  max-width: 760px;
}

.search-input {
  width: min(320px, 100%);
}

.filter-select {
  width: 150px;
}

.filter-count {
  display: inline-grid;
  min-width: 18px;
  height: 18px;
  margin-left: 6px;
  place-items: center;
  border-radius: 999px;
  background: var(--app-color-primary-soft);
  color: var(--app-color-primary);
  font-size: 12px;
  font-weight: 700;
}

.advanced-filter-panel {
  display: grid;
  gap: 14px;
}

.advanced-filter-panel label {
  display: grid;
  gap: 6px;
}

.advanced-filter-panel label > span {
  color: var(--app-color-text-muted);
  font-size: 12px;
}

.advanced-filter-panel :deep(.el-date-editor) {
  width: 100%;
}

.advanced-filter-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

@media (prefers-color-scheme: dark) {
  .advanced-filter-panel label > span {
    color: var(--app-color-text-muted);
  }
}

@media (max-width: 1080px) {
  .primary-toolbar {
    justify-content: flex-start;
    width: 100%;
    max-width: none;
  }
}

@media (max-width: 760px) {
  .toolbar,
  .search-input,
  .filter-select {
    width: 100%;
  }
}
</style>
