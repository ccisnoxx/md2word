<!-- frontend/src/components/WorkbenchPageHeader.vue: Shared workbench command header with title copy and right-side actions. -->
<template>
  <section :class="headerClasses" :aria-labelledby="titleId">
    <div :class="copyClasses">
      <p v-if="kicker" class="page-kicker">{{ kicker }}</p>
      <h1 :id="titleId" class="page-title">{{ title }}</h1>
      <p v-if="description" class="page-description">{{ description }}</p>
    </div>
    <div v-if="$slots.actions" :class="actionsClasses">
      <slot name="actions" />
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from "vue";

const props = withDefaults(
  defineProps<{
    titleId: string;
    title: string;
    kicker?: string;
    description?: string;
    wide?: boolean;
    sectionClass?: string | string[];
    copyClass?: string | string[];
    actionsClass?: string | string[];
  }>(),
  {
    kicker: "",
    description: "",
    wide: false,
    sectionClass: "",
    copyClass: "command-copy",
    actionsClass: "command-actions",
  },
);

const headerClasses = computed(() => [
  "app-workbench-header",
  "app-page-shell",
  props.wide ? "app-page-shell--wide" : "",
  props.sectionClass,
]);
const copyClasses = computed(() => ["app-workbench-header-copy", props.copyClass]);
const actionsClasses = computed(() => ["app-workbench-header-actions", props.actionsClass]);
</script>

<style scoped lang="scss">
.app-workbench-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--app-space-4);
  min-width: 0;
}

.app-workbench-header-copy {
  min-width: 0;
}

.app-workbench-header-copy .page-title {
  font-size: 24px;
}

.app-workbench-header-copy .page-description {
  margin-top: 6px;
}

.app-workbench-header-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  gap: var(--app-space-2);
  min-width: 0;
}

@media (max-width: 720px) {
  .app-workbench-header {
    flex-direction: column;
  }

  .app-workbench-header-actions {
    width: 100%;
    justify-content: flex-start;
  }
}
</style>
