<!-- 文件：frontend/src/features/word-page-styles/StyleFormPanel.vue -->
<!-- 用途：页面样式编辑器中间表单区，按后端白名单 schema 渲染分组 Tab 与受控样式控件。 -->
<template>
  <WorkbenchPanelCard
    :title="editor.activeCategory.value?.title || '样式分组'"
    :subtitle="editor.activeCategory.value?.description || '选择一个分组开始编辑。'"
    card-class="style-editor-panel"
    body-class="style-editor-panel-body"
  >
    <template #actions>
      <el-tag v-if="editor.activeCategoryDirtyCount.value > 0" type="warning" effect="plain">
        {{ editor.activeCategoryDirtyCount.value }} 项未保存
      </el-tag>
    </template>

    <div class="group-tabs" role="tablist" aria-label="样式分组">
      <button
        v-for="groupName in editor.activeCategoryGroups.value"
        :key="groupName"
        type="button"
        role="tab"
        :aria-selected="editor.activeLayoutGroup.value === groupName"
        :class="{ active: editor.activeLayoutGroup.value === groupName }"
        @click="editor.setActiveGroup(groupName)"
      >
        <span>{{ editor.layoutGroupTitle(groupName) }}</span>
        <el-tag v-if="editor.groupDirtyCount(groupName) > 0" size="small" type="warning" effect="plain">
          {{ editor.groupDirtyCount(groupName) }}
        </el-tag>
        <el-tag v-if="editor.groupHasErrors(groupName)" size="small" type="danger" effect="plain">校验</el-tag>
      </button>
    </div>

    <el-form label-position="top" class="layout-form">
      <section
        v-for="[groupName, groupSchema] in editor.visibleLayoutGroupEntries.value"
        :key="groupName"
        class="layout-section"
      >
        <header class="layout-section-heading">
          <div>
            <h3>{{ editor.layoutGroupTitle(groupName) }}</h3>
            <p>{{ editor.layoutGroupDescription(groupName) }}</p>
          </div>
        </header>

        <div class="layout-fields">
          <el-form-item
            v-for="[fieldName, fieldSchema] in editor.displayedFieldEntries(groupName, groupSchema)"
            :key="`${groupName}.${fieldName}`"
            :label="editor.fieldLabel(fieldName, fieldSchema)"
            :error="editor.fieldError(groupName, fieldName)"
          >
            <el-switch
              v-if="fieldSchema.type === 'boolean'"
              v-model="editor.layoutConfigForm.value[groupName][fieldName]"
              :disabled="Boolean(fieldSchema.readonly)"
              @change="editor.validateField(groupName, fieldName)"
            />
            <el-input-number
              v-else-if="fieldSchema.type === 'number'"
              v-model="editor.layoutConfigForm.value[groupName][fieldName]"
              :min="fieldSchema.min"
              :max="fieldSchema.max"
              :step="fieldSchema.step ?? 1"
              :disabled="Boolean(fieldSchema.readonly)"
              controls-position="right"
              @change="editor.validateField(groupName, fieldName)"
            />
            <el-segmented
              v-else-if="fieldSchema.type === 'alignment'"
              v-model="editor.layoutConfigForm.value[groupName][fieldName]"
              :options="editor.alignmentOptionsFor(fieldSchema)"
              :disabled="Boolean(fieldSchema.readonly)"
              @change="editor.validateField(groupName, fieldName)"
            />
            <div v-else-if="fieldSchema.type === 'color'" class="color-field">
              <el-color-picker
                v-model="editor.layoutConfigForm.value[groupName][fieldName]"
                :predefine="COLOR_PREDEFINES"
                :disabled="Boolean(fieldSchema.readonly)"
                @change="editor.validateField(groupName, fieldName)"
              />
              <el-input
                v-model="editor.layoutConfigForm.value[groupName][fieldName]"
                :disabled="Boolean(fieldSchema.readonly)"
                placeholder="#000000"
                @blur="editor.validateField(groupName, fieldName)"
              />
            </div>
            <el-input
              v-else-if="fieldSchema.type === 'text'"
              v-model="editor.layoutConfigForm.value[groupName][fieldName]"
              :disabled="Boolean(fieldSchema.readonly)"
              @blur="editor.validateField(groupName, fieldName)"
            />
            <el-alert v-else title="后端返回了当前页面不支持的字段类型，已阻止保存。" type="error" :closable="false" />
          </el-form-item>
        </div>
      </section>
    </el-form>
  </WorkbenchPanelCard>
</template>

<script setup lang="ts">
import WorkbenchPanelCard from "@/components/WorkbenchPanelCard.vue";
import { COLOR_PREDEFINES, type WordPageStyleEditor } from "./useWordPageStyleEditor";

defineProps<{
  editor: WordPageStyleEditor;
}>();
</script>

<style scoped lang="scss">
.style-editor-panel {
  min-width: 0;
  padding: var(--app-space-4);
}

.group-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: var(--app-space-2);
  margin-bottom: var(--app-space-4);
  padding-bottom: var(--app-space-3);
  border-bottom: 1px solid var(--app-color-border);
}

.group-tabs button {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 34px;
  padding: 7px 10px;
  border: 1px solid var(--app-color-border);
  border-radius: var(--app-radius-md);
  background: var(--app-color-surface);
  color: var(--app-color-text);
  cursor: pointer;
  transition: border-color 180ms ease, background-color 180ms ease;
}

.group-tabs button:hover,
.group-tabs button:focus-visible {
  border-color: var(--app-color-primary);
  outline: none;
}

.group-tabs button.active {
  border-color: var(--app-color-primary);
  background: var(--app-color-primary-soft);
  color: var(--app-color-primary-hover);
}

.layout-form {
  display: grid;
  gap: var(--app-space-3);
}

.layout-section-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.layout-section h3 {
  margin: 0;
  color: var(--app-color-text);
  font-size: 16px;
  font-weight: 650;
}

.layout-section-heading p {
  margin: 4px 0 0;
  color: var(--app-color-text-muted);
  font-size: 13px;
}

.layout-fields {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
  gap: var(--app-space-3) var(--app-space-4);
}

.layout-fields :deep(.el-form-item) {
  margin-bottom: 8px;
}

.layout-fields :deep(.el-input-number),
.layout-fields :deep(.el-select),
.layout-fields :deep(.el-segmented) {
  width: 100%;
}

.color-field {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 8px;
  align-items: center;
}
</style>
