<!-- frontend/src/components/WorkbenchEmptyState.vue: Shared empty state block for list workbenches. -->
<template>
  <div :class="emptyClasses" aria-live="polite">
    <el-icon v-if="icon" class="app-workbench-empty-icon"><component :is="icon" /></el-icon>
    <h3>{{ title }}</h3>
    <p>{{ description }}</p>
    <div v-if="$slots.actions" class="app-workbench-empty-actions">
      <slot name="actions" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, type Component } from "vue";

const props = withDefaults(
  defineProps<{
    title: string;
    description: string;
    icon?: Component | null;
    rootClass?: string | string[];
  }>(),
  {
    icon: null,
    rootClass: "",
  },
);

const emptyClasses = computed(() => ["app-workbench-empty-state", props.rootClass]);
</script>

<style scoped lang="scss">
.app-workbench-empty-state {
  display: grid;
  gap: var(--app-space-2);
  padding: var(--app-space-4);
  border: 1px solid var(--app-color-border-soft);
  border-radius: var(--app-radius-md);
  background: var(--app-color-surface-muted);
}

.app-workbench-empty-icon {
  color: var(--app-color-primary-hover);
  font-size: 26px;
}

.app-workbench-empty-state h3,
.app-workbench-empty-state p {
  margin: 0;
}

.app-workbench-empty-state h3 {
  color: var(--app-color-text);
  font-size: 16px;
}

.app-workbench-empty-state p {
  color: var(--app-color-text-muted);
  font-size: 13px;
}

.app-workbench-empty-actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--app-space-2);
}
</style>
