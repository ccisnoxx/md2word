<!-- frontend/src/components/WorkbenchDrawerSurface.vue: Shared right-drawer shell for evidence-heavy diagnostic and review workflows. -->
<template>
  <section :class="surfaceClasses" :aria-label="label">
    <header :class="headerClasses">
      <div class="app-drawer-surface-copy">
        <p v-if="kicker" class="page-kicker">{{ kicker }}</p>
        <h2>{{ title }}</h2>
        <p v-if="subtitle" class="app-drawer-surface-subtitle">{{ subtitle }}</p>
      </div>
      <div v-if="$slots.actions" class="app-drawer-surface-actions">
        <slot name="actions" />
      </div>
    </header>

    <div :class="bodyClasses">
      <slot />
    </div>

    <footer v-if="$slots.footer" :class="footerClasses">
      <slot name="footer" />
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed } from "vue";

const props = withDefaults(
  defineProps<{
    label: string;
    title: string;
    kicker?: string;
    subtitle?: string;
    rootClass?: string | string[];
    headerClass?: string | string[];
    bodyClass?: string | string[];
    footerClass?: string | string[];
  }>(),
  {
    kicker: "",
    subtitle: "",
    rootClass: "",
    headerClass: "",
    bodyClass: "",
    footerClass: "",
  },
);

const surfaceClasses = computed(() => ["app-drawer-surface", props.rootClass]);
const headerClasses = computed(() => ["app-drawer-surface-header", props.headerClass]);
const bodyClasses = computed(() => ["app-drawer-surface-body", props.bodyClass]);
const footerClasses = computed(() => ["app-drawer-surface-footer", props.footerClass]);
</script>

<style scoped lang="scss">
.app-drawer-surface {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr) auto;
  gap: var(--app-space-4);
  min-height: 100%;
  padding: 20px;
}

.app-drawer-surface-header,
.app-drawer-surface-footer {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--app-space-3);
}

.app-drawer-surface-copy,
.app-drawer-surface-actions,
.app-drawer-surface-body {
  min-width: 0;
}

.app-drawer-surface-copy h2 {
  margin: 0;
  color: var(--app-color-text);
  font-family: var(--app-font-heading);
  font-size: 22px;
  letter-spacing: -0.01em;
}

.app-drawer-surface-subtitle {
  margin: 4px 0 0;
  color: var(--app-color-text-muted);
}

.app-drawer-surface-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  gap: var(--app-space-2);
}

@media (max-width: 900px) {
  .app-drawer-surface-header,
  .app-drawer-surface-footer {
    align-items: stretch;
    flex-direction: column;
  }

  .app-drawer-surface-actions {
    width: 100%;
    justify-content: flex-start;
  }
}

@media (max-width: 760px) {
  .app-drawer-surface {
    padding: var(--app-space-3);
  }
}
</style>
