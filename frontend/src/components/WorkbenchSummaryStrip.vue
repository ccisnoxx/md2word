<!-- frontend/src/components/WorkbenchSummaryStrip.vue: Shared summary/inbox strip for list workbenches. -->
<template>
  <section :class="stripClasses" :aria-label="label">
    <button
      v-for="item in items"
      :key="item.id"
      type="button"
      :class="summaryItemClasses(item)"
      @click="emit('select', item.id)"
    >
      <span class="app-workbench-summary-count">{{ item.count }}</span>
      <span class="app-workbench-summary-copy">
        <strong>{{ item.label }}</strong>
        <small v-if="item.helper">{{ item.helper }}</small>
      </span>
    </button>
  </section>
</template>

<script setup lang="ts">
import { computed } from "vue";

type SummaryTone = "default" | "info" | "success" | "warning" | "danger";

export type WorkbenchSummaryStripItem = {
  id: string;
  label: string;
  helper?: string;
  count: number | string;
  tone?: SummaryTone;
  active?: boolean;
};

const props = withDefaults(
  defineProps<{
    label: string;
    items: WorkbenchSummaryStripItem[];
    wide?: boolean;
    sectionClass?: string | string[];
  }>(),
  {
    wide: false,
    sectionClass: "",
  },
);

const emit = defineEmits<{
  select: [id: string];
}>();

const stripClasses = computed(() => [
  "app-workbench-summary-strip",
  "app-page-shell",
  props.wide ? "app-page-shell--wide" : "",
  props.sectionClass,
]);

function summaryItemClasses(item: WorkbenchSummaryStripItem): Array<string | false> {
  const tone = item.tone && item.tone !== "default" ? `is-${item.tone}` : "";
  return ["app-workbench-summary-item", tone, item.active ? "is-active" : ""];
}
</script>

<style scoped lang="scss">
.app-workbench-summary-strip {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: var(--app-space-3);
}

.app-workbench-summary-item {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: var(--app-space-3);
  align-items: center;
  min-width: 0;
  min-height: 72px;
  padding: var(--app-space-3);
  border: 1px solid var(--app-color-border);
  border-radius: var(--app-radius-md);
  background: var(--app-color-surface);
  color: var(--app-color-text);
  text-align: left;
  box-shadow: var(--app-shadow-subtle);
  transition:
    border-color var(--app-motion-fast) ease-out,
    background-color var(--app-motion-fast) ease-out,
    box-shadow var(--app-motion-fast) ease-out,
    transform var(--app-motion-fast) var(--app-ease-out);
}

.app-workbench-summary-item:hover,
.app-workbench-summary-item:focus-visible,
.app-workbench-summary-item.is-active {
  border-color: var(--app-color-primary-border);
  background: var(--app-color-primary-soft);
  box-shadow: var(--app-shadow-focus);
  transform: translateY(-1px);
  outline: none;
}

.app-workbench-summary-item.is-success {
  border-color: var(--app-color-success-border);
}

.app-workbench-summary-item.is-warning {
  border-color: var(--app-color-warning-border);
}

.app-workbench-summary-item.is-danger {
  border-color: var(--app-color-danger-border);
}

.app-workbench-summary-count {
  display: inline-grid;
  min-width: 42px;
  height: 42px;
  place-items: center;
  border-radius: var(--app-radius-md);
  background: var(--app-color-primary-soft);
  color: var(--app-color-primary-hover);
  font-family: var(--app-font-heading);
  font-size: 20px;
  font-weight: 800;
  line-height: 1;
}

.app-workbench-summary-item.is-success .app-workbench-summary-count {
  background: var(--app-color-success-soft);
  color: var(--app-color-success);
}

.app-workbench-summary-item.is-warning .app-workbench-summary-count {
  background: var(--app-color-warning-soft);
  color: var(--app-color-warning);
}

.app-workbench-summary-item.is-danger .app-workbench-summary-count {
  background: var(--app-color-danger-soft);
  color: var(--app-color-danger);
}

.app-workbench-summary-copy {
  display: grid;
  gap: 3px;
  min-width: 0;
}

.app-workbench-summary-copy strong,
.app-workbench-summary-copy small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.app-workbench-summary-copy strong {
  color: var(--app-color-text);
  font-size: 14px;
}

.app-workbench-summary-copy small {
  color: var(--app-color-text-muted);
  font-size: 12px;
}
</style>
