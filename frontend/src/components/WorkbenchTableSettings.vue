<!-- 文件：frontend/src/components/WorkbenchTableSettings.vue -->
<!-- 用途：提供运维工作台可复用的本地表格偏好控件。 -->
<template>
  <el-popover
    v-model:visible="panelVisible"
    placement="bottom-end"
    trigger="click"
    :width="320"
    popper-class="workbench-table-settings-popper"
  >
    <template #reference>
      <el-button :icon="Setting" aria-label="表格设置">
        表格设置
      </el-button>
    </template>

    <section class="table-settings-panel" aria-label="表格设置面板">
      <div class="settings-section">
        <p :id="densityLabelId" class="settings-label">密度</p>
        <el-radio-group
          :model-value="modelValue.density"
          size="small"
          :aria-labelledby="densityLabelId"
          @change="handleDensityChange"
        >
          <el-radio-button label="standard">标准</el-radio-button>
          <el-radio-button label="compact">紧凑</el-radio-button>
        </el-radio-group>
      </div>

      <div class="settings-section">
        <p class="settings-label">显示列</p>
        <div class="column-list app-scrollbar-persistent">
          <el-checkbox
            v-for="column in columns"
            :key="column.id"
            :model-value="isColumnVisible(column.id)"
            :disabled="column.required"
            :aria-label="column.required ? `${column.label}，必要列，不能隐藏` : column.label"
            @change="handleColumnChange(column.id, $event)"
          >
            <span>{{ column.label }}</span>
            <small v-if="column.required">必要列，不能隐藏</small>
          </el-checkbox>
        </div>
      </div>

      <div class="settings-section">
        <label :id="pageSizeLabelId" class="settings-label">每页数量</label>
        <el-select
          :model-value="modelValue.pageSize"
          size="small"
          aria-label="每页数量"
          :aria-labelledby="pageSizeLabelId"
          @change="handlePageSizeChange"
        >
          <el-option :value="20" label="20 条/页" />
          <el-option :value="50" label="50 条/页" />
          <el-option :value="100" label="100 条/页" />
        </el-select>
      </div>

      <footer class="settings-footer">
        <el-button text size="small" @click="emit('reset')">恢复默认</el-button>
        <el-button size="small" @click="panelVisible = false">关闭</el-button>
      </footer>
    </section>
  </el-popover>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { Setting } from "@element-plus/icons-vue";

import {
  isWorkbenchTablePageSize,
  isWorkbenchTableColumnVisible,
  setWorkbenchTableColumnVisibility,
  type WorkbenchTableColumn,
  type WorkbenchTableDensity,
  type WorkbenchTablePageSize,
  type WorkbenchTablePreferences,
} from "@/utils/tablePreferences";

const props = defineProps<{
  settingsId: string;
  columns: WorkbenchTableColumn[];
  modelValue: WorkbenchTablePreferences;
}>();

const emit = defineEmits<{
  "update:modelValue": [preferences: WorkbenchTablePreferences];
  reset: [];
}>();

const panelVisible = ref(false);
const densityLabelId = computed(() => `${props.settingsId}-density-label`);
const pageSizeLabelId = computed(() => `${props.settingsId}-page-size-label`);

function isColumnVisible(columnId: string): boolean {
  return isWorkbenchTableColumnVisible(props.modelValue, columnId);
}

function handleDensityChange(value: string | number | boolean | undefined): void {
  const density = value === "compact" ? "compact" : "standard";
  emit("update:modelValue", { ...props.modelValue, density: density as WorkbenchTableDensity });
}

function handleColumnChange(columnId: string, checked: string | number | boolean): void {
  emit("update:modelValue", setWorkbenchTableColumnVisibility(props.modelValue, props.columns, columnId, Boolean(checked)));
}

function handlePageSizeChange(value: string | number | boolean | undefined): void {
  const pageSize = typeof value === "string" ? Number(value) : value;
  if (!isWorkbenchTablePageSize(pageSize)) {
    return;
  }
  emit("update:modelValue", { ...props.modelValue, pageSize: pageSize as WorkbenchTablePageSize });
}
</script>

<style scoped lang="scss">
.table-settings-panel {
  display: grid;
  gap: var(--app-space-3);
  color: var(--app-color-text);
}

.settings-section {
  display: grid;
  gap: 8px;
}

.settings-label {
  margin: 0;
  color: var(--app-color-text-muted);
  font-size: 12px;
  font-weight: 700;
}

.column-list {
  display: grid;
  gap: 6px;
  max-height: 240px;
  overflow-y: auto;
}

.column-list :deep(.el-checkbox) {
  align-items: flex-start;
  height: auto;
  margin-right: 0;
  white-space: normal;
}

.column-list :deep(.el-checkbox__label) {
  display: grid;
  gap: 2px;
  line-height: 1.35;
}

.column-list small {
  color: var(--app-color-text-faint);
  font-size: 11px;
}

.settings-section :deep(.el-select) {
  width: 100%;
}

.settings-footer {
  display: flex;
  justify-content: space-between;
  gap: var(--app-space-2);
  padding-top: var(--app-space-2);
  border-top: 1px solid var(--app-color-border-soft);
}

:global(.workbench-table-settings-popper) {
  max-width: calc(100vw - 24px);
}
</style>
