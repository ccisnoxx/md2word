<!-- frontend/src/components/WorkbenchMetricStrip.vue: Shared KPI/status card strip for dashboard and system workbench pages. -->
<template>
  <section :class="stripClasses" :aria-label="label">
    <article
      v-for="item in items"
      :key="item.id"
      :class="metricClasses(item)"
    >
      <span v-if="item.statusKey" class="app-status-dot" aria-hidden="true"></span>
      <div class="app-metric-copy">
        <span>{{ item.label }}</span>
        <strong :class="{ mono: item.mono }">{{ item.value }}</strong>
        <small>{{ item.helper }}</small>
      </div>
    </article>
  </section>
</template>

<script setup lang="ts">
import { computed } from "vue";

type MetricStatusKey = "ready" | "blocked" | "degraded" | "warning" | "success" | "danger" | "unknown" | "running";

export type WorkbenchMetricItem = {
  id: string;
  label: string;
  value: string | number;
  helper: string;
  statusKey?: MetricStatusKey | null;
  mono?: boolean;
};

const props = withDefaults(
  defineProps<{
    label: string;
    items: WorkbenchMetricItem[];
    wide?: boolean;
    sectionClass?: string | string[];
  }>(),
  {
    wide: false,
    sectionClass: "",
  },
);

const stripClasses = computed(() => [
  "app-metric-grid",
  "app-page-shell",
  props.wide ? "app-page-shell--wide" : "",
  props.sectionClass,
]);

function metricClasses(item: WorkbenchMetricItem): Array<string> {
  const classes = ["app-metric-card"];
  if (item.statusKey) {
    classes.push("app-status-card", `is-${item.statusKey}`);
  }
  return classes;
}
</script>

<style scoped lang="scss">
.app-metric-copy {
  min-width: 0;
}

.app-metric-copy strong.mono {
  font-family: var(--app-font-mono);
  font-size: 20px;
}
</style>
