<!-- File: frontend/src/components/ShortcutHintList.vue -->
<!-- Purpose: Render compact Chinese shortcut hints consistently across operation surfaces. -->
<template>
  <div class="shortcut-hint-list" :aria-label="ariaLabel">
    <span v-for="item in items" :key="`${item.keys.join('+')}:${item.label}`" class="shortcut-hint-item">
      <template v-for="(key, index) in item.keys" :key="`${item.label}:${key}:${index}`">
        <kbd>{{ key }}</kbd>
        <span v-if="index < item.keys.length - 1" class="shortcut-plus" aria-hidden="true">+</span>
      </template>
      <span>{{ item.label }}</span>
    </span>
  </div>
</template>

<script setup lang="ts">
import type { ShortcutHint } from "@/utils/keyboardShortcuts";

withDefaults(
  defineProps<{
    items: ShortcutHint[];
    ariaLabel?: string;
  }>(),
  {
    ariaLabel: "快捷键提示",
  },
);
</script>

<style scoped lang="scss">
.shortcut-hint-list {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  color: var(--app-color-text-muted);
  font-size: 12px;
}

.shortcut-hint-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  min-width: 0;
}

kbd {
  display: inline-grid;
  min-width: 22px;
  min-height: 20px;
  place-items: center;
  padding: 1px 6px;
  border: 1px solid var(--app-color-border);
  border-radius: var(--app-radius-sm);
  background: var(--app-color-surface);
  color: var(--app-color-text);
  font-family: var(--app-font-mono);
  font-size: 11px;
  line-height: 1.2;
}

.shortcut-plus {
  color: var(--app-color-text-faint);
}
</style>

