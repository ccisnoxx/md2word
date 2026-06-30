<!-- frontend/src/components/EvidenceKeyValueList.vue: Shared key/value evidence rows for identifiers, trace fields, and compact technical facts. -->
<template>
  <dl :class="listClasses">
    <div v-for="item in items" :key="item.label" class="app-evidence-kv-row">
      <dt>{{ item.label }}</dt>
      <dd :class="{ mono: item.mono }">
        <strong>{{ item.value }}</strong>
        <small v-if="item.helper">{{ item.helper }}</small>
      </dd>
    </div>
  </dl>
</template>

<script setup lang="ts">
import { computed } from "vue";

export type EvidenceKeyValueItem = {
  label: string;
  value: string;
  helper?: string;
  mono?: boolean;
};

const props = withDefaults(
  defineProps<{
    items: EvidenceKeyValueItem[];
    rootClass?: string | string[];
  }>(),
  {
    rootClass: "",
  },
);

const listClasses = computed(() => ["app-evidence-kv-list", props.rootClass]);
</script>

<style scoped lang="scss">
.app-evidence-kv-list {
  display: grid;
  gap: 8px;
  margin: 0;
}

.app-evidence-kv-row {
  display: grid;
  grid-template-columns: 110px minmax(0, 1fr);
  gap: 10px;
}

.app-evidence-kv-row dt {
  color: var(--app-color-text-muted);
  font-size: 12px;
}

.app-evidence-kv-row dd {
  min-width: 0;
  margin: 0;
}

.app-evidence-kv-row strong,
.app-evidence-kv-row small {
  display: block;
  overflow-wrap: anywhere;
}

.app-evidence-kv-row strong {
  color: var(--app-color-text);
  font-size: 13px;
  font-weight: 600;
}

.app-evidence-kv-row small {
  margin-top: 3px;
  color: var(--app-color-text-muted);
  font-size: 12px;
}

.mono {
  font-family: var(--app-font-mono);
}

@media (max-width: 720px) {
  .app-evidence-kv-row {
    grid-template-columns: 1fr;
    gap: 4px;
  }
}
</style>
