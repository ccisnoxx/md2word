<!-- frontend/src/components/WorkbenchGovernanceMetricStrip.vue: Shared compact governance summary strip for blockers, drafts, diff counts, and review metrics. -->
<template>
  <section :class="stripClasses" :aria-label="label">
    <article
      v-for="item in items"
      :key="item.id"
      :class="metricClasses(item)"
    >
      <span>{{ item.label }}</span>
      <strong :class="{ mono: item.mono }">{{ item.value }}</strong>
      <small>{{ item.helper }}</small>
    </article>
  </section>
</template>

<script setup lang="ts">
import { computed } from "vue";

type MetricTone = "default" | "success" | "warning" | "danger" | "info";

export type WorkbenchGovernanceMetricItem = {
  id: string;
  label: string;
  value: string | number;
  helper: string;
  tone?: MetricTone;
  mono?: boolean;
};

const props = withDefaults(
  defineProps<{
    label: string;
    items: WorkbenchGovernanceMetricItem[];
    sectionClass?: string | string[];
  }>(),
  {
    sectionClass: "",
  },
);

const stripClasses = computed(() => ["app-governance-grid", props.sectionClass]);

function metricClasses(item: WorkbenchGovernanceMetricItem): string[] {
  return ["app-governance-metric", item.tone && item.tone !== "default" ? `is-${item.tone}` : ""];
}
</script>

<style scoped lang="scss">
.app-governance-metric strong.mono {
  font-family: var(--app-font-mono);
  font-size: 16px;
}
</style>
