<!-- frontend/src/components/EvidenceSurfaceSection.vue: Shared heading/body wrapper for evidence-heavy detail and drawer sections. -->
<template>
  <component :is="tag" :class="sectionClasses" :aria-label="ariaLabel || title">
    <header v-if="title || description || $slots.actions" class="app-evidence-section-heading">
      <div class="app-evidence-section-copy">
        <h3 v-if="title">{{ title }}</h3>
        <p v-if="description">{{ description }}</p>
      </div>
      <div v-if="$slots.actions" class="app-evidence-section-actions">
        <slot name="actions" />
      </div>
    </header>
    <div class="app-evidence-section-body">
      <slot />
    </div>
  </component>
</template>

<script setup lang="ts">
import { computed } from "vue";

const props = withDefaults(
  defineProps<{
    title?: string;
    description?: string;
    ariaLabel?: string;
    tag?: string;
    rootClass?: string | string[];
    compact?: boolean;
  }>(),
  {
    title: "",
    description: "",
    ariaLabel: "",
    tag: "section",
    rootClass: "",
    compact: false,
  },
);

const sectionClasses = computed(() => [
  "app-evidence-section",
  props.compact ? "is-compact" : "",
  props.rootClass,
]);
</script>

<style scoped lang="scss">
.app-evidence-section {
  display: grid;
  gap: var(--app-space-3);
  min-width: 0;
  padding: var(--app-space-3);
  border: 1px solid var(--app-color-border);
  border-radius: var(--app-radius-md);
  background: var(--app-color-surface);
}

.app-evidence-section.is-compact {
  gap: var(--app-space-2);
}

.app-evidence-section-heading {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--app-space-2);
}

.app-evidence-section-copy,
.app-evidence-section-actions,
.app-evidence-section-body {
  min-width: 0;
}

.app-evidence-section-copy h3,
.app-evidence-section-copy p {
  margin: 0;
}

.app-evidence-section-copy h3 {
  color: var(--app-color-text);
  font-size: 15px;
}

.app-evidence-section-copy p {
  margin-top: 4px;
  color: var(--app-color-text-muted);
  font-size: 12px;
  line-height: 1.45;
}

.app-evidence-section-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  gap: var(--app-space-2);
}

@media (max-width: 720px) {
  .app-evidence-section-actions {
    width: 100%;
    justify-content: flex-start;
  }
}
</style>
