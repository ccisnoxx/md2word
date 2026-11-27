<!-- 文件：frontend/src/features/word-page-styles/StyleCategoryRail.vue -->
<!-- 用途：页面样式编辑器左侧一级大类导航栏，带未保存项角标。 -->
<template>
  <aside class="category-rail" aria-label="样式大类">
    <button
      v-for="category in editor.availableCategories.value"
      :key="category.id"
      type="button"
      :class="{ active: editor.activeCategoryId.value === category.id }"
      @click="editor.setActiveCategory(category.id)"
    >
      <span>{{ category.title }}</span>
      <small>{{ category.description }}</small>
      <el-tag v-if="editor.categoryDirtyCount(category.id) > 0" size="small" type="warning" effect="plain">
        {{ editor.categoryDirtyCount(category.id) }}
      </el-tag>
    </button>
  </aside>
</template>

<script setup lang="ts">
import type { WordPageStyleEditor } from "./useWordPageStyleEditor";

defineProps<{
  editor: WordPageStyleEditor;
}>();
</script>

<style scoped lang="scss">
.category-rail {
  position: sticky;
  top: 86px;
  display: grid;
  gap: var(--app-space-2);
}

.category-rail button {
  position: relative;
  display: grid;
  gap: 4px;
  min-height: 68px;
  padding: var(--app-space-3);
  border: 1px solid var(--app-color-border);
  border-radius: var(--app-radius-md);
  background: var(--app-color-surface);
  color: var(--app-color-text);
  text-align: left;
  cursor: pointer;
  transition: border-color 180ms ease, background-color 180ms ease, box-shadow 180ms ease;
}

.category-rail button:hover,
.category-rail button:focus-visible {
  border-color: var(--app-color-primary-border);
  box-shadow: var(--app-shadow-subtle);
  outline: none;
}

.category-rail button.active {
  border-color: var(--app-color-primary-border);
  background: var(--app-color-primary-soft);
}

.category-rail button span {
  font-weight: 650;
}

.category-rail button small {
  color: var(--app-color-text-muted);
  line-height: 1.4;
}

.category-rail button :deep(.el-tag) {
  position: absolute;
  top: 10px;
  right: 10px;
}

@media (max-width: 820px) {
  .category-rail {
    position: static;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  }
}
</style>
