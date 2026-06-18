<!-- frontend/src/components/TerminologyWorkbenchNav.vue: Shared navigation for terminology governance subviews. -->
<template>
  <section class="terminology-workbench-nav app-panel-card" aria-label="术语工作台子视图">
    <div class="workbench-copy">
      <p class="workbench-kicker">Terminology Governance</p>
      <h2>术语工作台</h2>
      <p>{{ activeDescription }}</p>
    </div>
    <nav class="workbench-tabs" aria-label="术语工作台">
      <router-link
        v-for="option in options"
        :key="option.key"
        class="workbench-tab"
        :class="{ active: option.key === active }"
        :to="option.to"
      >
        <span>{{ option.label }}</span>
        <small>{{ option.helper }}</small>
      </router-link>
    </nav>
  </section>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { useRoute, type RouteLocationRaw } from "vue-router";

type TerminologyWorkbenchView = "draft-publish" | "live-rules";

const props = defineProps<{
  active: TerminologyWorkbenchView;
}>();

const route = useRoute();

const preservedGovernanceQuery = computed(() => {
  const query: Record<string, string> = {};
  for (const key of ["proposal_id", "source_term", "target_rule_id", "return_tab", "set_id"]) {
    const value = route.query[key];
    if (typeof value === "string" && value.trim()) {
      query[key] = value;
    }
  }
  return query;
});

const draftPublishRoute = computed<RouteLocationRaw>(() => ({
  name: "settings-term-rule-sets",
  query: preservedGovernanceQuery.value,
}));

const liveRulesRoute = computed<RouteLocationRaw>(() => ({
  name: "settings-term-rules",
  query: preservedGovernanceQuery.value,
}));

const options = computed(() => [
  {
    key: "draft-publish" as const,
    label: "草稿与发布",
    helper: "draft / diff / preflight / publish",
    to: draftPublishRoute.value,
  },
  {
    key: "live-rules" as const,
    label: "当前生效规则",
    helper: "live inspection / simulation",
    to: liveRulesRoute.value,
  },
]);

const activeDescription = computed(() =>
  props.active === "draft-publish"
    ? "生产修改进入 draft，发布或切默认后才影响后续默认版本和 runtime 同步。"
    : "当前视图只读检查 live runtime store，用于确认实际转换路径正在消费的规则。",
);
</script>

<style scoped lang="scss">
.terminology-workbench-nav {
  display: flex;
  align-items: stretch;
  justify-content: space-between;
  gap: 16px;
  padding: 16px;
  border: 1px solid var(--app-color-border);
  border-radius: var(--app-radius-md);
  background: var(--app-color-surface);
}

.workbench-copy {
  display: grid;
  gap: 4px;
  min-width: 0;
}

.workbench-kicker {
  margin: 0;
  color: var(--app-color-primary);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0;
  text-transform: uppercase;
}

.workbench-copy h2 {
  margin: 0;
  color: var(--app-color-text);
  font-size: 18px;
  line-height: 1.25;
}

.workbench-copy p:last-child {
  margin: 0;
  color: var(--app-color-text-muted);
  font-size: 13px;
  line-height: 1.5;
}

.workbench-tabs {
  display: grid;
  grid-template-columns: repeat(2, minmax(150px, 1fr));
  gap: 8px;
  min-width: min(420px, 100%);
}

.workbench-tab {
  display: grid;
  gap: 4px;
  padding: 10px 12px;
  border: 1px solid var(--app-color-border);
  border-radius: var(--app-radius-md);
  background: var(--app-color-surface-muted);
  color: var(--app-color-text);
}

.workbench-tab.active {
  border-color: var(--app-color-primary-border);
  background: var(--app-color-primary-soft);
  color: var(--app-color-primary-hover);
}

.workbench-tab span {
  font-size: 14px;
  font-weight: 700;
}

.workbench-tab small {
  color: var(--app-color-text-muted);
  font-size: 12px;
  line-height: 1.35;
}

.workbench-tab.active small {
  color: var(--app-color-primary-hover);
}

@media (max-width: 820px) {
  .terminology-workbench-nav {
    flex-direction: column;
  }

  .workbench-tabs {
    grid-template-columns: 1fr;
    min-width: 0;
  }
}
</style>
