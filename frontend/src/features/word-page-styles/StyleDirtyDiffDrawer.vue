<!-- 文件：frontend/src/features/word-page-styles/StyleDirtyDiffDrawer.vue -->
<!-- 用途：展示页面样式全部未保存字段差异列表，支持点击定位到对应分组及批量撤销。 -->
<template>
  <el-drawer
    v-model="editor.dirtyDrawerOpen.value"
    :title="`未保存改动明细（${editor.dirtyFieldCount.value} 项）`"
    direction="rtl"
    size="min(520px, 94vw)"
    :append-to-body="true"
  >
    <div class="diff-drawer-body app-scrollbar-persistent">
      <div v-if="!editor.dirtySummaries.value.length" class="diff-empty">
        当前没有未保存的样式改动。
      </div>
      <ul v-else class="diff-list" aria-label="全部未保存样式改动">
        <li v-for="item in editor.dirtySummaries.value" :key="item.path" class="diff-item">
          <div class="diff-item-head">
            <strong>{{ item.label }}</strong>
            <el-button size="small" link type="primary" @click="jumpToGroup(item.groupName)">定位</el-button>
          </div>
          <span class="mono diff-path">{{ item.path }}</span>
          <div class="diff-values">
            <span class="diff-before">{{ item.before }}</span>
            <span>→</span>
            <span class="diff-after">{{ item.after }}</span>
          </div>
        </li>
      </ul>
    </div>

    <template #footer>
      <div class="diff-drawer-footer">
        <el-button :disabled="!editor.isLayoutDirty.value" @click="editor.resetLayoutConfigForm()">
          撤销全部改动
        </el-button>
        <el-button
          type="primary"
          :loading="editor.layoutConfigSaving.value"
          :disabled="!editor.isLayoutDirty.value"
          @click="editor.saveLayoutConfigVersion()"
        >
          保存为草稿版本
        </el-button>
      </div>
    </template>
  </el-drawer>
</template>

<script setup lang="ts">
import type { WordPageStyleEditor } from "./useWordPageStyleEditor";

const props = defineProps<{
  editor: WordPageStyleEditor;
}>();

function jumpToGroup(groupName: string): void {
  props.editor.setActiveGroup(groupName);
  props.editor.dirtyDrawerOpen.value = false;
}
</script>

<style scoped lang="scss">
.diff-drawer-body {
  max-height: calc(100vh - 150px);
  overflow-y: auto;
  padding-right: 4px;
}

.diff-empty {
  padding: 24px 12px;
  text-align: center;
  color: var(--app-color-text-muted);
  font-size: 13px;
}

.diff-list {
  display: grid;
  gap: 10px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.diff-item {
  display: grid;
  gap: 4px;
  padding: 10px 12px;
  border: 1px solid var(--app-color-border-soft);
  border-radius: var(--app-radius-md);
  background: var(--app-color-surface-soft);
}

.diff-item-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  font-size: 13px;
}

.diff-path {
  font-size: 11px;
  color: var(--app-color-text-faint);
}

.diff-values {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  font-size: 12px;
}

.diff-before {
  color: var(--app-color-text-muted);
  text-decoration: line-through;
}

.diff-after {
  color: var(--app-color-primary);
  font-weight: 650;
}

.diff-drawer-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>
