<!-- frontend/src/components/WorkbenchSectionHeader.vue: Shared list-workbench section intro with optional kicker and right-side slot. -->
<template>
  <div :class="headerClasses">
    <div class="app-workbench-section-copy">
      <p v-if="kicker" class="page-kicker">{{ kicker }}</p>
      <h2 class="section-title">{{ title }}</h2>
      <p v-if="subtitle" class="section-subtitle">{{ subtitle }}</p>
    </div>
    <div v-if="$slots.extra" :class="extraClasses">
      <slot name="extra" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";

const props = withDefaults(
  defineProps<{
    title: string;
    kicker?: string;
    subtitle?: string;
    headerClass?: string | string[];
    extraClass?: string | string[];
  }>(),
  {
    kicker: "",
    subtitle: "",
    headerClass: "",
    extraClass: "",
  },
);

const headerClasses = computed(() => ["app-workbench-section-header", "section-header", props.headerClass]);
const extraClasses = computed(() => ["app-workbench-section-extra", props.extraClass]);
</script>

<style scoped lang="scss">
.app-workbench-section-header {
  align-items: flex-start;
}

.app-workbench-section-copy,
.app-workbench-section-extra {
  min-width: 0;
}

.app-workbench-section-extra {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  gap: var(--app-space-2);
}

@media (max-width: 720px) {
  .app-workbench-section-extra {
    width: 100%;
    justify-content: flex-start;
  }
}
</style>
