<template>
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
      <el-option v-for="stage in documentJobStages" :key="stage" :label="jobStageText[stage] || stage" :value="stage" />
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
    <WorkbenchTableSettings
      :model-value="tablePreferences"
      settings-id="incident-table-settings"
      :columns="incidentTableColumns"
      @update:model-value="handleTablePreferencesUpdate"
      @reset="handleTablePreferencesReset"
    />
  </div>
</template>

<script setup lang="ts">
import type { UnwrapRef } from "vue";
import { Filter, Refresh, Search } from "@element-plus/icons-vue";
import WorkbenchTableSettings from "@/components/WorkbenchTableSettings.vue";
import { documentJobStages, jobStageText, jobStatusText } from "@/utils/format";
import {
  incidentFailureTypeText,
  incidentFailureTypes,
  incidentRetryCountBucketText,
  incidentRetryCountBuckets,
  incidentSortOptions,
  incidentSortText,
} from "@/utils/incidents";
import { statuses } from "./incidentQuery";
import type { IncidentQueue } from "./useIncidentQueue";

const searchKeyword = defineModel<UnwrapRef<IncidentQueue["searchKeyword"]>>("searchKeyword", { required: true });
const statusFilter = defineModel<UnwrapRef<IncidentQueue["statusFilter"]>>("statusFilter", { required: true });
const stageFilter = defineModel<UnwrapRef<IncidentQueue["stageFilter"]>>("stageFilter", { required: true });
const failureTypeFilter = defineModel<UnwrapRef<IncidentQueue["failureTypeFilter"]>>("failureTypeFilter", { required: true });
const retryableFilter = defineModel<UnwrapRef<IncidentQueue["retryableFilter"]>>("retryableFilter", { required: true });
const retryCountFilter = defineModel<UnwrapRef<IncidentQueue["retryCountFilter"]>>("retryCountFilter", { required: true });
const stalledMinutesFilter = defineModel<UnwrapRef<IncidentQueue["stalledMinutesFilter"]>>("stalledMinutesFilter", { required: true });
const sortFilter = defineModel<UnwrapRef<IncidentQueue["sortFilter"]>>("sortFilter", { required: true });
const {
  loading,
  advancedFilterCount,
  tablePreferences,
  incidentTableColumns,
  handleFilter,
  resetAdvancedFilters,
  handleTablePreferencesUpdate,
  handleTablePreferencesReset,
} = defineProps<{
  loading: UnwrapRef<IncidentQueue["loading"]>;
  advancedFilterCount: UnwrapRef<IncidentQueue["advancedFilterCount"]>;
  tablePreferences: UnwrapRef<IncidentQueue["tablePreferences"]>;
  incidentTableColumns: IncidentQueue["incidentTableColumns"];
  handleFilter: IncidentQueue["handleFilter"];
  resetAdvancedFilters: IncidentQueue["resetAdvancedFilters"];
  handleTablePreferencesUpdate: IncidentQueue["handleTablePreferencesUpdate"];
  handleTablePreferencesReset: IncidentQueue["handleTablePreferencesReset"];
}>();
</script>

<style scoped lang="scss">
.toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--app-space-2);
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

@media (max-width: 900px) {
  .filter-toolbar > * {
    width: 100% !important;
  }
}
</style>
